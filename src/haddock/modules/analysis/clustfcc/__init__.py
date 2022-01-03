"""HADDOCK3 FCC clustering module."""
import os
from pathlib import Path

from fcc.scripts import calc_fcc_matrix, cluster_fcc

from haddock import FCC_path, log
from haddock.gear.config_reader import read_config
from haddock.libs.libontology import ModuleIO
from haddock.libs.libparallel import Scheduler
from haddock.libs.libsubprocess import Job
from haddock.modules import BaseHaddockModule


RECIPE_PATH = Path(__file__).resolve().parent
DEFAULT_CONFIG = Path(RECIPE_PATH, "defaults.cfg")


class HaddockModule(BaseHaddockModule):
    """HADDOCK3 module for clustering with FCC."""

    name = RECIPE_PATH.name

    def __init__(self, order, path, initial_params=DEFAULT_CONFIG):
        super().__init__(order, path, initial_params)

    @classmethod
    def confirm_installation(cls):
        """Confirm if FCC is installed and available."""
        dcfg = read_config(DEFAULT_CONFIG)
        exec_path = Path(FCC_path, dcfg['executable'])

        if not os.access(exec_path, mode=os.F_OK):
            raise Exception(f'Required {str(exec_path)} file does not exist.')

        if not os.access(exec_path, mode=os.X_OK):
            raise Exception(f'Required {str(exec_path)} file is not executable')

        return

    def _run(self):
        """Execute module."""
        contact_executable = Path(FCC_path, self.params['executable'])

        # Get the models generated in previous step
        models_to_cluster = self.previous_io.retrieve_models()

        # Calculate the contacts for each model
        log.info('Calculating contacts')
        contact_jobs = []
        for model in models_to_cluster:
            pdb_f = Path(model.rel_path)
            contact_f = Path(model.file_name.replace('.pdb', '.con'))
            job = Job(
                pdb_f,
                contact_f,
                contact_executable,
                self.params['contact_distance_cutoff'],
                arg_first=True,
                )
            contact_jobs.append(job)

        contact_engine = Scheduler(contact_jobs, ncores=self.params['ncores'])
        contact_engine.run()

        contact_file_l = []
        not_found = []
        for job in contact_jobs:
            if not job.output.exists():
                # NOTE: If there is no output, most likely the models are not in
                # contact there is no way of knowing how many models are not in
                # contact, it can be only one, or could be all of them.
                not_found.append(job.input.name)
                log.warning(f'Contact was not calculated for {job.input.name}')
            else:
                contact_file_l.append(str(job.output))

        if not_found:
            # No contacts were calculated, we cannot cluster
            self.finish_with_error("Several files were not generated:"
                                   f" {not_found}")

        log.info('Calculating the FCC matrix')
        parsed_contacts = calc_fcc_matrix.parse_contact_file(contact_file_l, False)  # noqa: E501

        # Imporant: matrix is a generator object, be careful with it
        matrix = calc_fcc_matrix.calculate_pairwise_matrix(parsed_contacts, False)  # noqa: E501

        # write the matrix to a file, so we can read it afterwards and don't
        #  need to reinvent the wheel handling this
        fcc_matrix_f = Path('fcc.matrix')
        with open(fcc_matrix_f, 'w') as fh:
            for data in list(matrix):
                data_str = f"{data[0]} {data[1]} {data[2]:.2f} {data[3]:.3f}"
                data_str += os.linesep
                fh.write(data_str)
        fh.close()

        # Cluster
        log.info('Clustering...')
        pool = cluster_fcc.read_matrix(
            fcc_matrix_f,
            self.params['fraction_cutoff'],
            self.params['strictness'],
            )

        _, clusters = cluster_fcc.cluster_elements(
            pool,
            threshold=self.params['threshold'],
            )

        # Prepare output and read the elements
        clt_dic = {}
        if clusters:
            # write the classic output file for compatibility reasons
            log.info('Saving output to cluster.out')
            cluster_out = Path('cluster.out')
            with open(cluster_out, 'w') as fh:
                cluster_fcc.output_clusters(fh, clusters)
            fh.close()

            for clt in clusters:
                cluster_id = clt.name
                clt_dic[cluster_id] = []
                # cluster_center = clt.center.name
                for model in clt.members:
                    model_id = model.name
                    pdb = models_to_cluster[model_id - 1]
                    clt_dic[cluster_id].append(pdb)

            # Rank the clusters
            #  they are sorted by the top4 models in each cluster
            top_n = 4
            score_dic = {}
            for clt_id in clt_dic:
                score_l = [p.score for p in clt_dic[clt_id]]
                score_l.sort()
                top4_score = sum(score_l[:top_n]) / float(top_n)
                score_dic[clt_id] = top4_score

            sorted_score_dic = sorted(score_dic.items(), key=lambda k: k[1])

            # Add this info to the models
            clustered_models = []
            for cluster_rank, _e in enumerate(sorted_score_dic, start=1):
                cluster_id, _ = _e
                # sort the models by score
                model_score_l = [(e.score, e) for e in clt_dic[cluster_id]]
                model_score_l.sort()
                # rank the models
                for model_ranking, element in enumerate(model_score_l, start=1):
                    score, pdb = element
                    pdb.clt_id = cluster_id
                    pdb.clt_rank = cluster_rank
                    pdb.clt_model_rank = model_ranking
                    clustered_models.append(pdb)

            # Prepare clustfcc.txt
            output_fname = Path('clustfcc.txt')
            output_str = f'### clustfcc output ###{os.linesep}'
            output_str += os.linesep
            output_str += f'Clustering parameters {os.linesep}'
            output_str += (
                "> contact_distance_cutoff="
                f"{self.params['contact_distance_cutoff']}A"
                f"{os.linesep}")
            output_str += (
                f"> fraction_cutoff={self.params['fraction_cutoff']}"
                f"{os.linesep}")
            output_str += f"> threshold={self.params['threshold']}{os.linesep}"
            output_str += (
                f"> strictness={self.params['strictness']}{os.linesep}")
            output_str += (
                f"-----------------------------------------------{os.linesep}")
            output_str += os.linesep
            output_str += f'Total # of clusters: {len(clusters)}{os.linesep}'

            for cluster_rank, _e in enumerate(sorted_score_dic, start=1):
                cluster_id, _ = _e
                model_score_l = [(e.score, e) for e in clt_dic[cluster_id]]
                model_score_l.sort()
                top_score = sum(
                    [e[0] for e in model_score_l][:top_n]
                    ) / top_n
                output_str += (
                    f"{os.linesep}"
                    "-----------------------------------------------"
                    f"{os.linesep}"
                    f"Cluster {cluster_rank} (#{cluster_id}, "
                    f"n={len(model_score_l)}, "
                    f"top{top_n}_avg_score = {top_score:.2f})"
                    f"{os.linesep}")
                output_str += os.linesep
                output_str += f'clt_rank\tmodel_name\tscore{os.linesep}'
                for model_ranking, element in enumerate(model_score_l, start=1):
                    score, pdb = element
                    output_str += (
                        f"{model_ranking}\t{pdb.file_name}\t{score:.2f}"
                        f"{os.linesep}")
            output_str += (
                "-----------------------------------------------"
                f"{os.linesep}")

            log.info('Saving detailed output to clustfcc.txt')
            with open(output_fname, 'w') as out_fh:
                out_fh.write(output_str)
        else:
            log.warning('No clusters were found')
            clustered_models = models_to_cluster

        # Save module information
        io = ModuleIO()
        io.add(clustered_models, "o")
        io.save()

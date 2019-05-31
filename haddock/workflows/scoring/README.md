### Conversion of scoring analysis scripts to Python


This script will:

1. Extract HADDOCK information from the PDB header
2. Calculate RMSDs using the best haddock-structure as reference with `profit`
3. Calculate FCC Matrix via `calc_fcc_matrix.py` using `contact_fcc`
4. Cluster with `cluster_fcc.py`

All steps were taken from `/ana_scripts/ana_rescored.csh`, PDBs used for input have been trought `scoring.inp` (step 3 or original protocol). Compile `contact_fcc.cpp` before using this script 

*Note: Structures in `/pdbs` are dimers from Round 46, Target 155 of CAPRI.* 

### Todo
* Install and implement third-party software: `dfire`, `fastcontact`, `molprobity`, `DockQ` and `PPI3D`
* Improve and expand pre-processing of scoring set (naming, numbering, chain matching, etc)


***

## Original scoring protocol

All tools/scripts used for this are in `/scripts` and `/cns_scripts`, analysis routines are in `/ana_scripts`

* Keep this for reference

```bash
######################
# 0) prepare PDB files
######################

   gunzip Target160.pdb.gz 
   grep MD5 Target160.pdb >Target160.MD5
   mkdir pdbs
   grep -v REMAR Target160.pdb | grep -v CTERB | grep -v CTERA |grep -v NTERA |grep -v NTERB |grep -v CONECT > target160-noremarks.pdb
   scripts/pdb_chain-segid target160-noremarks.pdb > tt
   pdb_xseg tt | sed -e 's/\ 0\.00969/\ 0\.00\ \ \ /g' |sed -e 's/WAT\ /TIP3/g' |sed -e 's/HSD/HIS/g' | sed -e 's/HSE/HIS/g' |sed -e 's/HID/HIS/' |sed -e 's/HIE/HIS/' > pdbs/target160-noremarks.pdb
   cd pdbs
   ../scripts/splitpdb target160-noremarks.pdb
   foreach i (_*)
     ../scripts/pdb_chain-segid $i >target160-scoring$i.pdb
     \rm $i
   end

##########################
# 1) make list of all pdbs
##########################
# copy first one of our submission (the top one) to target160-haddock-top-model.pdb so that the numbering will be based on this one

  ll target160-haddock-top-model.pdb target160-scoring_*[0-9].pdb | awk '{print $9}' > pdb.list

# correct the PDBs with no chainID -> NOT NEEDED
#
#foreach i (`ll | sort -nk6 | awk '$5 > 422594 && $5 < 422598' | awk '{print $9}'`)
#  head -2746 $i |pdb_chain -A |grep -v END > t1
#  tail -2744 $i |pdb_chain -B >> t1
#  \mv t1 $i
#end
#
#foreach i ( target160-scoring_0013.pdb )
#  head -2597 $i |pdb_chain -A |grep -v END > t1
#  tail -2595 $i |pdb_chain -B >> t1
#  \mv t1 $i
#end

################################################################################
# 2) match chain IDs and common fragments, but first delete all waters from PDBs
################################################################################

   ~software/haddock/haddock_scripts/PDB-matching/match_chains.csh pdb.list

################################################################################
# 3) in the pdb-matched directory generate filelist.list containing the PDBs with full
   directory path to be analysed, edit the scoring.inp file if needed and run the analysis
   (run_scoring.csh)
################################################################################
   
   ~software/haddock/haddock_scripts/make_filelist

   # check filelist.list and remove commonA/B files and the haddock model
   #
   # adapt following command to split the filelist.list files into pieces of 100 structures
   # based on the total number of models to score

   head -100 filelist.list| tail -100  > filelist1.list
   head -200 filelist.list| tail -100  > filelist2.list
   head -300 filelist.list| tail -100  > filelist3.list
   head -400 filelist.list| tail -100  > filelist4.list
   head -500 filelist.list| tail -100  > filelist5.list
   head -600 filelist.list| tail -100  > filelist6.list
   head -700 filelist.list| tail -100  > filelist7.list
   head -800 filelist.list| tail -100  > filelist8.list
   head -900 filelist.list| tail -100  > filelist9.list
   head -1000 filelist.list| tail -100  > filelist10.list
   head -1100 filelist.list| tail -100  > filelist11.list
   head -1200 filelist.list| tail -100  > filelist12.list
   head -1300 filelist.list| tail -100  > filelist13.list
   head -1400 filelist.list| tail -100  > filelist14.list
   head -1500 filelist.list| tail -100  > filelist15.list
   head -1600 filelist.list| tail -100  > filelist16.list
   head -1700 filelist.list| tail -100  > filelist17.list
   head -1800 filelist.list| tail -100  > filelist18.list
   head -1900 filelist.list| tail -100  > filelist19.list
   head -2000 filelist.list| tail -100  > filelist20.list
   head -2100 filelist.list| tail -100  > filelist21.list
   head -2200 filelist.list| tail -100  > filelist22.list
   head -2300 filelist.list| tail -100  > filelist23.list
   head -2400 filelist.list| tail -100  > filelist24.list
   head -2500 filelist.list| tail -100  > filelist25.list


   # run the scoring scripts:
   # 0) copy all files from cns-scripts in the working directorys	
   # 1) edit and modify oif needed the scoring.inp script
   #  - define the proper protonation state of histidines using one of our HADDOCK run
   #    look into the corresponding run.cns and check the histidine numbers - search for hisd / hise and edit these in scoring.inp
   #  - If you have a homodimer, you might turn on symmetry. Define for that the start and end residues 
   #    and the segid for the symmetrical chains
   #    Turn on the sym flag
   # 2) copy ligand parameters from a HADDOCK run in directory if required
   # 3) edit the make-scoringfile to define the number of separate run file 
   #    (should match the number of filelistX.list files) and source it
   #    This will create separe run-scoringX.csh files
   # 4) run or submit to queue the run_scoring#.csh scripts
   
4) all converted files copied to ../../rescored

   mkdir ../../rescored
   mv *conv.pdb *conv.psf ../../rescored
   cd ../../rescored

5) Edit the analysis scripts

   # copy the best converted haddock model (from pdb-matched) into ana_scripts/target160_refe.pdb
   # create molscript input:

   molauto -nice target160_refe.pdb > target160_refe.molin

   # edit run_analysis-selected.csh  and replace the molscript lines (the ones with coil, beta, helix...) by the ones in target160_refe.molin

6) run the analysis
   ../ana_scripts/ana_rescored.csh


NOTES: Some models contain knots!!! You should always visualize the complexes
       Removed them manually from the cluster list and rerun the analysis 

7) To find out where are our own models go into the haddock-server-models
   # copy, unzip and split the PDB containing our 100 models, e.g.

   cp ../Target160/server-selection/target160-HADDOCKserver-top100.pdb.gz
   gunzip target160-HADDOCKscoring-top100.pdb.gz 
   ../scripts/splitpdb target160-HADDOCKserver-top100.pdb
   foreach i (_*)  
     mv $i target160-HADDOCKserver-top100$i.pdb
   end
   rm target160-HADDOCKserver-top100.pdb
   sed -e 's/tar/\.\.\/rescored\/tar/g' ../rescored/file.nam >file.nam

   #edit and check the zone/rzone definitions to make sure the residues do exist (some might have been deleted in the rescored models)

   ./run-find.csh

   # then check the *ranking* files to figure our where our models are

```
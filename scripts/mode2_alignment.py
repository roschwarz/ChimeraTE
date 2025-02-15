import argparse
import datetime
import subprocess
import glob
import pandas as pd
import re
import csv
from io import StringIO
from __main__ import *
import pybedtools
import contextlib
import sys
import os

def alignment_func(out_dir, aln_dir, mate1, mate2):
    clock = time()
    print(str(clock) + '\t' + "Perfoming bowtie2 alignment for TEs...")
    subprocess.call(['bowtie2', '-x', str(out_dir + '/index/TE_index'), '-1', str(mate1), '-2', str(mate2), '-D', '20', '-R', '3', '-N', '1', '-L', '20', '-i', 'S,1,0.50', '-p', str(args.threads), '-S', str(aln_dir + '/tes.sam')], stdout=subprocess.DEVNULL)
    print(colored("Done!", "green", attrs=['bold']))

    clock = time()
    print(str(clock) + '\t' + "Perfoming bowtie2 alignment for transcripts...")
    subprocess.call(['bowtie2', '-x', str(out_dir + '/index/transcripts_index'), '-1', str(mate1), '-2', str(mate2), '-D', '20', '-R', '3', '-N', '1', '-L', '20', '-i', 'S,1,0.50', '-p', str(args.threads), '-S', str(aln_dir + '/genes.sam')], stdout=subprocess.DEVNULL)
    print(colored("Done!", "green", attrs=['bold']))

    sam = ['tes', 'genes']
    for samf in sam:
        with open(str(aln_dir + '/' + str(samf) + '.bam'), 'w') as f:
            subprocess.call(['samtools', 'view', '-@', str(args.threads), '-bS', str(aln_dir + '/' + samf + '.sam')], stdout=f, stderr=subprocess.DEVNULL)
        f.close()
        os.remove(str(aln_dir + '/' + samf + '.sam'))
        with open(str(aln_dir + '/' + str(samf) + '.bed'), 'w') as f:
            subprocess.call(['bedtools', 'bamtobed', '-i', str(aln_dir + '/' + samf + '.bam')], stdout=f)
        f.close()

    tes_bed = pd.read_csv(str(aln_dir + '/tes.bed'), sep="\t", usecols=[0,1,2,3,4,5], names=['TE_id','2','3','4','5','6'])
    tes_bed['TE_id'] = tes_bed['TE_id'].replace('_n.*$', '', regex=True)
    tes_bed.to_csv(aln_dir + '/tes.bed', header=None, index=False, sep='\t')

    clock = time()
    print(str(clock) + '\t' + "Calculating transcripts expression...")
    subprocess.call(['express', '-o', str(aln_dir + '/fpkm_counts'), '-O', '1', '--output-align-prob', '--no-bias-correct', str('--' + str(args.strand)), str(args.transcripts), str(aln_dir + '/genes.bam')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if check_file(str(aln_dir + '/fpkm_counts/hits.1.prob.bam')) == True:
        os.remove(str(aln_dir + '/fpkm_counts/hits.1.prob.bam'))
        fpkm_gene = pd.read_csv(str(aln_dir + '/fpkm_counts/results.xprs'), sep="\t", usecols=[1,12])
        fpkm_gene.loc[fpkm_gene['fpkm_conf_high'] > 1].loc[:,['target_id']].drop_duplicates().to_csv(aln_dir + '/genes_expressed_IDs.lst', header=None, index=False)
    else:
        print(colored("Unable to calculate expression due to low rate of alignment! Including all transcripts to the downstream analysis...", "yellow", attrs=['bold']))
        df = pd.read_csv(str(aln_dir + '/genes.bed'), header=None, sep="\t", usecols=[0],names=['gene_id']).drop_duplicates().to_csv(aln_dir + '/genes_expressed_IDs.lst', header=None, index=False)
    print(colored("Done!", "green", attrs=['bold']))

    clock = time()
    print(str(clock) + '\t' + "Identifying chimeric reads...")
    with open(str(aln_dir + '/genes_expressed_IDs.lst')) as f:
        list_genes = f.read().splitlines()
    df = pd.read_csv(str(aln_dir + '/genes.bed'), header=None, sep="\t", usecols=[0,1,2,3,4,5],names=['scaf', 'start', 'end', 'ID', 'dot', 'strand'])
    df[df['scaf'].isin(list_genes)].to_csv(str(aln_dir + '/genes_total_expressed.bed'), header=None, index=False, sep="\t")
    print(colored("Done!", "green", attrs=['bold']))

    clock = time()
    TE_read1 = mate_spec_IDs(str(aln_dir + '/tes.bed'), str('1'))
    TE_read1 = StringIO(TE_read1)
    TE_read2 = mate_spec_IDs(str(aln_dir + '/tes.bed'), str('2'))
    TE_read2 = StringIO(TE_read2)

    genes_read1 = mate_spec_IDs(str(aln_dir + '/genes_total_expressed.bed'), str('1'))
    gr1_list = genes_read1.splitlines()

    genes_read2 = mate_spec_IDs(str(aln_dir + '/genes_total_expressed.bed'), str('2'))
    gr2_list = genes_read2.splitlines()

    df = pd.read_table(TE_read1, header=None, sep="\t", usecols=[0],names=['read_ID'])
    chim_TE1_gene2 = df[df['read_ID'].isin(gr2_list)].drop_duplicates()

    df = pd.read_table(TE_read2, header=None, sep="\t", usecols=[0],names=['read_ID'])
    chim_TE2_gene1 = df[df['read_ID'].isin(gr1_list)].drop_duplicates()

    if chim_TE1_gene2 is not None and chim_TE2_gene1 is not None:
        merged_reads = pd.concat([chim_TE1_gene2, chim_TE2_gene1]).drop_duplicates().to_csv(header=None, index=False, sep="\t")
        merged_reads_list = merged_reads.splitlines()
        overlap(str(aln_dir + '/tes.bed'), merged_reads_list, str(aln_dir + '/TEs_chim.bed'))
        overlap(str(aln_dir + '/genes_total_expressed.bed'), merged_reads_list, str(aln_dir + '/genes_chim.bed'))
    print(colored("Done!", "green", attrs=['bold']))





#

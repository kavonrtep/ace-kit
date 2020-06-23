
import warnings

import logomaker
import pandas
import numpy
from numpy.lib.stride_tricks import as_strided

from matplotlib import pyplot

colors = {
    'A': 'blue',
    'C': 'yellow',
    'G': 'green',
    'T': 'red',
    '-': 'black'
}


rc = {
    'A': 'T',
    'C': 'G',
    'G': 'C',
    'T': 'A',
    '-': '-',
    'N': 'N'
}


def revcomp(seq):
    seq = seq.replace('*', '-')
    return "".join([rc[x] for x in seq[::-1]])


def compute_end_pos(read):
    return read.start + read.length


def window(
    array:numpy.ndarray, window:int,
    shift:int=1, copy:bool=False
):
    shape = (array.size - window + 1, window)
    stride = array.strides * 2

    view = as_strided(
        array, strides=stride, shape=shape
    )[0::shift]

    if copy:
        return view.copy()

    else:
        return view


def create_seqlogo_dataframe(sequences):
    seqlen = len(sequences[0])
    idx = pandas.Index(data=range(seqlen), name='pos')
    basemat = numpy.array([list(x) for x in sequences]).T
    df = pandas.DataFrame(
        numpy.zeros(shape=(seqlen, len(colors))), index=idx, columns=colors.keys()
    )

    for x in colors:
        df[x] = (basemat == x).sum(axis=1)

    freqs = df / len(sequences)

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', r'divide by zero encountered in log2')
        log_freqs = numpy.nan_to_num(numpy.log2(freqs))

    correction = (1 / numpy.log(2)) * (4/(2*len(sequences)))
    row_scale = numpy.log2(5) - (- (freqs * log_freqs) + correction).sum(axis=1)

    return freqs.multiply(row_scale, axis=0)


def create_logo(sequences, figsize=(10, 2.5), save=None):

    fig, ax = pyplot.subplots(1, figsize=figsize)

    df = create_seqlogo_dataframe(sequences)

    logo = logomaker.Logo(df, color_scheme=colors, ax=ax)
    logo.style_xticks(anchor=0, spacing=5, rotation=45)
    logo.ax.set_xlim([-1, len(df)])
    logo.ax.set_ylabel('information (bits)')

    return logo, fig


def extract_seqs(ctg, cands, derivs, ext=30):
    """
        cands is a list of positions (0-based) where reads should overlap
        derivs is the value of the derivative at that position (+, -)
    """
    seqs_pos = []
    seqs_neg = []
    count = 0
    read_ids = []
    for r in ctg.reads:
        b = r.start
        e = r.start + r.length
        for c, d in zip(cands, derivs):
            if ((c - ctg.shift) in range(b, e)):
                pos = c - ctg.shift - b
                seq = r.seq
                seq = seq.replace("*", "-")
                if d > 0:
                    seqs_pos.append(seq[pos:pos+ext])
                else:
                    seqs_neg.append(seq[pos-ext+1:pos+1])
                count += 1
                read_ids.append(r.name)

    seqs_pos = [x for x in seqs_pos if len(x) == ext]
    seqs_neg = [x for x in seqs_neg if len(x) == ext]

    mate_ids = []
    for _id in read_ids:
        if _id.endswith("f"):
            mate_ids.append(f"{_id[:-1]}r")
        else:
            mate_ids.append(f"{_id[:-1]}f")
    read_ids = set(read_ids + mate_ids)

    return count, read_ids, seqs_pos, seqs_neg


def get_reads_from_candidate(contig, pos):
    reads = []
    for read in contig.reads:
        b = read.start
        e = read.start + read.length
        if (pos - contig.shift) in range(b, e):
            pos_in_read = pos - contig.shift - b
            read.boundary = pos_in_read
            reads.append(read)
    return reads


def find(s, ch, start=1):
    return [i for i, ltr in enumerate(s, start=start) if ltr == ch]


def remove_gaps_and_adjust_boundary(read):
    positions = list(range(1, read.length + 1))
    gaps_pos = find(read.seq, '*')
    for gap in gaps_pos:
        positions.pop(positions.index(gap))
    if read.boundary:
        new_boundary_location = positions.index(read.boundary) + 1
        read.boundary = new_boundary_location
    read.seq = read.seq.replace("*", "")
    read.length = len(read.seq)
    read.t = read.length if read.length < read.t else read.t


def sign(x):
    return 1 - (x <= 0)


def find_all_boundary_reads(boundaries):
    boundary_reads = {}
    for b in boundaries:
        reads_on_b = b.get_reads_from_boundary()
        for read in reads_on_b:
            read.boundary = 1
            read.side = b.side
        boundary_reads.update({x.name: x for x in reads_on_b})

    return boundary_reads


def pair_boundary_reads(boundary_reads, all_reads):
    paired_boundary = {}
    for br in boundary_reads:
        if br[:-1] in paired_boundary:
            continue
        else:
            other_end = "f" if br[-1] == "r" else "r"
            other_id = f"{br[:-1]}{other_end}"
            if other_id in all_reads:
                paired_boundary[br[:-1]] = [boundary_reads[br], all_reads[other_id]]
                paired_boundary[br[:-1]].sort(key=lambda x: x.name[-1])

    return paired_boundary


def pairs_with_correct_orient(paired_reads_dict):
    oriented = {}
    for x in paired_reads_dict:
        l, r = paired_reads_dict[x]
        if l.comp != r.comp:
            oriented[x] = (l, r)
    return oriented

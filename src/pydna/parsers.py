#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2013-2023 by Björn Johansson.  All rights reserved.
# This code is part of the Python-dna distribution and governed by its
# license.  Please see the LICENSE.txt file that should have been included
# as part of this package.

"""Provides two functions, parse and parse_primers"""

import os as _os
import re as _re
import io as _io
import textwrap as _textwrap

from Bio import SeqIO as _SeqIO
from pydna.genbankfile import GenbankFile as _GenbankFile
from pydna.dseqrecord import Dseqrecord as _Dseqrecord
from pydna.primer import Primer as _Primer
from pydna.amplify import pcr as _pcr
from copy import deepcopy as _deepcopy
from Bio.SeqFeature import SeqFeature as _SeqFeature
import xml.etree.ElementTree as _et

try:
    from itertools import pairwise as _pairwise
except ImportError:

    def _pairwise(iterable):
        # pairwise('ABCDEFG') → AB BC CD DE EF FG
        iterator = iter(iterable)
        a = next(iterator, None)
        for b in iterator:
            yield a, b
            a = b


# "^>.+?^(?=$|LOCUS|ID|>|\#)|^(?:LOCUS|ID).+?^//"
# "(?:^>.+\n^(?:^[^>]+?)(?=\n\n|>|^LOCUS|ID))|(?:(?:^LOCUS|ID)(?:(?:.|\n)+?)^//)"

gb_fasta_embl_regex = r"(?:>.+\n^(?:^[^>]+?)(?=\n\n|>|LOCUS|ID))|(?:(?:LOCUS|ID)(?:(?:.|\n)+?)^//)"

# The gb_fasta_embl_regex is meant to be able to extract sequences from
# text where sequences are mixed with other contents as well
# use https://regex101.com to get an idea how it works.


# def extract_from_text(text):
#     return _re.finditer(gb_fasta_embl_regex, _textwrap.dedent(str(text) + "\n\n"), flags=_re.MULTILINE)


def extract_from_text(text):
    data = _textwrap.dedent(str(text))
    mos = list(_re.finditer(gb_fasta_embl_regex, data + "\n\n", flags=_re.MULTILINE))

    class mo(object):

        def start(self):
            return len(data)

        def end(self):
            return 0

    mofirst = molast = mo()

    gaps = []

    for mo1, mo2 in _pairwise([mofirst] + mos + [molast]):
        gaps.append(data[mo1.end() : mo2.start()])

    return [mo.group(0) for mo in mos], gaps


def embl_gb_fasta(text, ds, path=None):

    chunks, gaps = extract_from_text(text)
    result_list = []

    for chunk in chunks:
        handle = _io.StringIO(chunk)
        circular = False
        try:
            parsed = _SeqIO.read(handle, "embl")
        except ValueError:
            handle.seek(0)
            try:
                parsed = _SeqIO.read(handle, "genbank")
                if "circular" in str(parsed.annotations.get("topology")).lower():
                    circular = True
            except ValueError:
                handle.seek(0)
                try:
                    parsed = _SeqIO.read(handle, "fasta")
                except ValueError:
                    parsed = ""
        handle.close()
        if "circular" in chunk.splitlines()[0].lower().split():
            # hack to pick up topology from malformed files
            circular = True
        if parsed:
            # TODO: clean up !
            nfs = [_SeqFeature() for f in parsed.features]
            for f, nf in zip(parsed.features, nfs):
                nf.__dict__ = _deepcopy(f.__dict__)
            parsed.features = nfs
            if ds and path:
                result_list.append(_GenbankFile.from_SeqRecord(parsed, circular=circular, path=path))
            elif ds:
                result_list.append(_Dseqrecord.from_SeqRecord(parsed, circular=circular))
            else:
                parsed.annotations.update({"molecule_type": "DNA"})
                result_list.append(parsed)

    return result_list


def parse(data, ds=True):
    """Return *all* DNA sequences found in data.

    If no sequences are found, an empty list is returned. This is a greedy
    function, use carefully.

    Parameters
    ----------
    data : string or iterable
        The data parameter is a string containing:

        1. an absolute path to a local file.
           The file will be read in text
           mode and parsed for EMBL, FASTA
           and Genbank sequences. Can be
           a string or a Path object.

        2. a string containing one or more
           sequences in EMBL, GENBANK,
           or FASTA format. Mixed formats
           are allowed.

        3. data can be a list or other iterable where the elements are 1 or 2

    ds : bool
        If True double stranded :class:`Dseqrecord` objects are returned.
        If False single stranded :class:`Bio.SeqRecord` [#]_ objects are
        returned.

    Returns
    -------
    list
        contains Dseqrecord or SeqRecord objects

    References
    ----------
    .. [#] http://biopython.org/wiki/SeqRecord

    See Also
    --------
    read

    """

    # a string is an iterable datatype but on Python2.x
    # it doesn't have an __iter__ method.
    if not hasattr(data, "__iter__") or isinstance(data, (str, bytes)):
        data = (data,)

    sequences = []

    for item in data:
        try:
            # item is a path to a utf-8 encoded text file?
            with open(item, "r", encoding="utf-8") as f:
                raw = f.read()
        except IOError:
            # item was not a path, add sequences parsed from item
            raw = item
            path = None
        else:
            # item was a readable text file, seqences are parsed from the file
            path = item
        finally:
            sequences.extend(embl_gb_fasta(raw, ds, path))
    return sequences


def parse_primers(data):
    """docstring."""
    return [_Primer(x) for x in parse(data, ds=False)]


def parse_assembly_xml(data):
    """docstring."""
    root = _et.fromstring(data)
    results = []
    for child in root:
        if child.tag == "amplicon":
            fp, rp, tmpl, *rest = parse(child.text)
            results.append(_pcr(_Primer(fp), _Primer(rp), tmpl, limit=min((len(fp), len(rp)))))
        elif child.tag == "fragment":
            f, *rest = parse(child.text)
            results.append(f)
    return results


if __name__ == "__main__":
    cached = _os.getenv("pydna_cached_funcs", "")
    _os.environ["pydna_cached_funcs"] = ""
    import doctest

    doctest.testmod(verbose=True, optionflags=doctest.ELLIPSIS)
    _os.environ["pydna_cached_funcs"] = cached

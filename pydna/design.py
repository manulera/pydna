#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2013, 2014 by Björn Johansson.  All rights reserved.
# This code is part of the Python-dna distribution and governed by its
# license.  Please see the LICENSE.txt file that should have been included
# as part of this package.

'''
This module contain functions for primer design.

'''
#import warnings

import math                                       as _math
#from operator import itemgetter                   as _itemgetter
import os                                         as _os
import copy                                       as _copy
#from Bio.Alphabet import Alphabet                 as _Alphabet
#from Bio.Alphabet.IUPAC import IUPACAmbiguousDNA  as _IUPACAmbiguousDNA
#from Bio.Seq import Seq                           as _Seq
from pydna.amplify import Anneal                  as _Anneal
from pydna.amplify import pcr                     as _pcr
from pydna.tm import tmbresluc                    as _tmbresluc
from pydna.dseqrecord import Dseqrecord           as _Dseqrecord
#from pydna._pretty import pretty_str              as _pretty_str
from pydna.primer    import Primer                as _Primer

import logging    as _logging
_module_logger = _logging.getLogger("pydna."+__name__)

def primer_design(    template,
                      fp=None,
                      rp=None,
                      target_tm=55.0,
                      fprimerc=1000.0,  # nM
                      rprimerc=1000.0,  # nM
                      saltc=50.0,
                      limit=13,
                      formula = _tmbresluc):

    '''This function designs a forward primer and a reverse primer for PCR amplification 
    of a given template sequence.
    
    The template argument is a Dseqrecord object or equivalent containing the template sequence.
    
    The optional fp and rp arguments can contain an existing primer for the sequence (either the forward or reverse primer).
    One or the other primers can be specified, not both (since then there is nothing to design!, use the pydna.amplify.pcr function instead).
    
    If one ofthe primers is given, the other primer is designed to match in terms of Tm.
    If both primers are designed, they will be designed to target_tm
    
    fprimerc, rprimerc and saltc are formward and reverse primer concentration (nM). Saltc is the salt concentration. 
    These arguments might affect how Tm is calculated.
    
    formula is a function that can take at least three arguments f( str, primerc=float, saltc=float).
    There are several of these in the pydna.tm module.
    
    The function returns a pydna.amplicon.Amplicon class instance. This object has 
    the object.forward_primer and object.reverse_primer properties which contain the designed primers.
    
    
    Parameters
    ----------

    template : pydna.dseqrecord.Dseqrecord
        a Dseqrecord object. The only required argument.

    fp, rp : pydna.primer.Primer, optional
        optional pydna.primer.Primer objects containing one primer each.

    target_tm : float, optional
        target tm for the primers, set to 55°C by default.

    fprimerc : float, optional
        Concentration of forward primer in nM, set to 1000.0 nM by default.

    rprimerc : float, optional
        Concentration of reverse primer in nM, set to 1000.0 nM by default.

    saltc  : float, optional
        Salt concentration (monovalet cations) :mod:`tmbresluc` set to 50.0 mM by default

    formula : function
        formula used for tm calculation
        this is the name of a function.
        built in options are:

        1. :func:`pydna.amplify.tmbresluc` (default)
        2. :func:`pydna.amplify.basictm`
        3. :func:`pydna.amplify.tmstaluc98`
        4. :func:`pydna.amplify.tmbreslauer86`

        These functions are imported from the :mod:`pydna.amplify` module, but can be
        substituted for some other custom made function.

    Returns
    -------
    result : Amplicon

    Examples
    --------

    >>> from pydna.dseqrecord import Dseqrecord
    >>> t=Dseqrecord("atgactgctaacccttccttggtgttgaacaagatcgacgacatttcgttcgaaacttacgatg")
    >>> t
    Dseqrecord(-64)
    >>> from pydna.design import primer_design
    >>> ampl = primer_design(t)
    >>> ampl
    Amplicon(64)
    >>> ampl.forward_primer
    fw64 18-mer:5'-atgactgctaacccttcc-3'
    >>> ampl.reverse_primer
    rv64 19-mer:5'-catcgtaagtttcgaacga-3'
    >>> print(ampl.figure())
    5atgactgctaacccttcc...tcgttcgaaacttacgatg3
                          ||||||||||||||||||| tm 53.8 (dbd) 60.6
                         3agcaagctttgaatgctac5
    5atgactgctaacccttcc3
     |||||||||||||||||| tm 54.4 (dbd) 58.4
    3tactgacgattgggaagg...agcaagctttgaatgctac5
    >>> pf = "GGATCC" + ampl.forward_primer
    >>> pr = "GGATCC" + ampl.reverse_primer  
    >>> pf
    fw64 24-mer:5'-GGATCCatgactgct..tcc-3'
    >>> pr
    rv64 25-mer:5'-GGATCCcatcgtaag..cga-3'
    >>> from pydna.amplify import pcr
    >>> pcr_prod = pcr(pf, pr, t)
    >>> print(pcr_prod.figure())
          5atgactgctaacccttcc...tcgttcgaaacttacgatg3
                                ||||||||||||||||||| tm 53.8 (dbd) 60.6
                               3agcaagctttgaatgctacCCTAGG5
    5GGATCCatgactgctaacccttcc3
           |||||||||||||||||| tm 54.4 (dbd) 58.4
          3tactgacgattgggaagg...agcaagctttgaatgctac5
    >>> print(pcr_prod.seq)
    GGATCCatgactgctaacccttccttggtgttgaacaagatcgacgacatttcgttcgaaacttacgatgGGATCC
    >>> from pydna.primer import Primer
    >>> pf = Primer("atgactgctaacccttccttggtgttg", id="myprimer")
    >>> ampl = primer_design(t, fp = pf)
    >>> ampl.forward_primer
    myprimer 27-mer:5'-atgactgctaaccct..ttg-3'
    >>> ampl.reverse_primer
    rv64 28-mer:5'-catcgtaagtttcga..gtc-3'

    '''
    
    def design(target_tm, template):
        ''' returns a string '''
        tmp=0
        length=limit
        p = str(template.seq[:length])
        while tmp<target_tm:
            length+=1
            p = str(template.seq[:length])
            tmp = formula(p.upper())
        ps = p[:-1]
        tmps = formula(str(ps).upper())
        _module_logger.debug(((p,   tmp),(ps, tmps)))
        return min( ( abs(target_tm-tmp), p), (abs(target_tm-tmps), ps) )[1]
    
    if fp and not rp:
        fp  = _Anneal((fp,), template).forward_primers.pop()
        target_tm = formula( str(fp.footprint), primerc=fprimerc, saltc=saltc)
        _module_logger.debug("forward primer given, design reverse primer:")
        rp = _Primer(design(target_tm, template.rc()))
    elif not fp and rp:
        rp =  _Anneal([rp], template).reverse_primers.pop()
        target_tm = formula( str(rp.footprint), primerc=rprimerc, saltc=saltc)
        _module_logger.debug("reverse primer given, design forward primer:")
        fp = _Primer(design(target_tm, template))
    elif not fp and not rp:
        _module_logger.debug("no primer given, design forward primer:")
        fp = _Primer((design(target_tm, template)))
        target_tm = formula( str(fp.seq), primerc=fprimerc, saltc=saltc)
        _module_logger.debug("no primer given, design reverse primer:")
        rp = _Primer(design(target_tm, template.rc()))
    else:
        raise Exception("Specify maximum one of the two primers.")

    ampl = _Anneal( (fp, rp), template, limit=limit)
    
    prod = ampl.products[0]
    
    prod.forward_primer.concentration = fprimerc
    prod.reverse_primer.concentration = rprimerc
    
    ## TODO primer id should be set to something based on the template id

    if prod.forward_primer.id == "id?": #<unknown id>
        prod.forward_primer.id = "fw{}".format(len(template))
        
    if prod.reverse_primer.id == "id?":
        prod.reverse_primer.id = "rv{}".format(len(template))

    if prod.forward_primer.name == "id?":
        prod.forward_primer.name = "fw{}".format(len(template))
        
    if prod.reverse_primer.name == "id?":
        prod.reverse_primer.name = "rv{}".format(len(template))

    prod.forward_primer.description = prod.forward_primer.id+' '+template.accession
    prod.reverse_primer.description = prod.reverse_primer.id+' '+template.accession

    return prod

def assembly_fragments(f, overlap=35, maxlink=40):
    
    '''This function return a list of :mod:`pydna.amplicon.Amplicon` objects where 
    primers have been modified with tails so that the fragments can be fused in 
    the order they appear in the list by for example Gibson assembly or homologous 
    recombination.
    
    Given that we have two linear :mod:`pydna.amplicon.Amplicon` objects a and b 
    
    we can modify the reverse primer of a and forward primer of b with tails to allow 
    fusion by fusion PCR, Gibson assembly or in-vivo homologous recombination.
    The basic requirements for the primers for the three techniques are the same.

    ::
        
                                <-->

       _________ a _________           __________ b ________
      /                     \\         /                     \\
      agcctatcatcttggtctctgca         TTTATATCGCATGACTCTTCTTT
      |||||||||||||||||||||||         |||||||||||||||||||||||
                       <gacgt                          <AGAAA
      agcct>                          TTTAT>
      |||||||||||||||||||||||         |||||||||||||||||||||||
      tcggatagtagaaccagagacgt         AAATATAGCGTACTGAGAAGAAA


           agcctatcatcttggtctctgcaTTTATATCGCATGACTCTTCTTT
           ||||||||||||||||||||||||||||||||||||||||||||||
           tcggatagtagaaccagagacgtAAATATAGCGTACTGAGAAGAAA
           \\___________________ c ______________________/


    Design tailed primers incorporating a part of the next or previous fragment to be assembled.

    ::


      agcctatcatcttggtctctgca
      |||||||||||||||||||||||
                      gagacgtAAATATA

      |||||||||||||||||||||||
      tcggatagtagaaccagagacgt


                             TTTATATCGCATGACTCTTCTTT
                             |||||||||||||||||||||||

                      ctctgcaTTTATAT
                             |||||||||||||||||||||||
                             AAATATAGCGTACTGAGAAGAAA

    PCR products with flanking sequences are formed in the PCR process.

    ::

      agcctatcatcttggtctctgcaTTTATAT
      ||||||||||||||||||||||||||||||
      tcggatagtagaaccagagacgtAAATATA
                      \\____________/

                         identical
                         sequences
                       ____________
                      /            \\
                      ctctgcaTTTATATCGCATGACTCTTCTTT
                      ||||||||||||||||||||||||||||||
                      gagacgtAAATATAGCGTACTGAGAAGAAA

    The fragments can be fused by any of the techniques mentioned earlier to form c:

    ::

      agcctatcatcttggtctctgcaTTTATATCGCATGACTCTTCTTT
      ||||||||||||||||||||||||||||||||||||||||||||||
      tcggatagtagaaccagagacgtAAATATAGCGTACTGAGAAGAAA


    The first argument of this function is a list of sequence objects containing 
    Amplicons and other similar objects.
    
    **At least every second sequence object needs to be an Amplicon**
    
    This rule exists because if a sequence object is that is not a PCR product
    is to be fused with another fragment, that other fragment needs to be an Amplicon
    so that the primer of the other object can be modified to include the whole stretch
    of sequence homology needed for the fusion. See the example below where a is a 
    non-amplicon (a linear plasmid  vector for instance)

    ::

       _________ a _________           __________ b ________
      /                     \\         /                     \\
      agcctatcatcttggtctctgca   <-->  TTTATATCGCATGACTCTTCTTT
      |||||||||||||||||||||||         |||||||||||||||||||||||
      tcggatagtagaaccagagacgt                          <AGAAA
                                      TTTAT>
                                      |||||||||||||||||||||||
                                <-->  AAATATAGCGTACTGAGAAGAAA


           agcctatcatcttggtctctgcaTTTATATCGCATGACTCTTCTTT
           ||||||||||||||||||||||||||||||||||||||||||||||
           tcggatagtagaaccagagacgtAAATATAGCGTACTGAGAAGAAA
           \\___________________ c ______________________/


    In this case only the forward primer of b is fitted with a tail with a part a:

    ::


      agcctatcatcttggtctctgca
      |||||||||||||||||||||||
      tcggatagtagaaccagagacgt


                             TTTATATCGCATGACTCTTCTTT
                             |||||||||||||||||||||||
                                              <AGAAA
               tcttggtctctgcaTTTATAT
                             |||||||||||||||||||||||
                             AAATATAGCGTACTGAGAAGAAA

    PCR products with flanking sequences are formed in the PCR process.

    ::

      agcctatcatcttggtctctgcaTTTATAT
      ||||||||||||||||||||||||||||||
      tcggatagtagaaccagagacgtAAATATA
                      \\____________/

                         identical
                         sequences
                       ____________
                      /            \\
                      ctctgcaTTTATATCGCATGACTCTTCTTT
                      ||||||||||||||||||||||||||||||
                      gagacgtAAATATAGCGTACTGAGAAGAAA

    The fragments can be fused by for example Gibson assembly:

    ::

      agcctatcatcttggtctctgcaTTTATAT
      ||||||||||||||||||||||||||||||
      tcggatagtagaacca
                      
                                   TCGCATGACTCTTCTTT
                      ||||||||||||||||||||||||||||||
                      gagacgtAAATATAGCGTACTGAGAAGAAA 
                      
    to form c:

    ::
                
      agcctatcatcttggtctctgcaTTTATATCGCATGACTCTTCTTT
      ||||||||||||||||||||||||||||||||||||||||||||||
      tcggatagtagaaccagagacgtAAATATAGCGTACTGAGAAGAAA
      

    The first argument of this function is a list of sequence objects containing 
    Amplicons and other similar objects.
    
    The overlap argument controls how many base pairs of overlap required between 
    adjacent sequence fragments. In the junction between Amplicons, tails with the 
    length of about half of this value is added to the two primers
    closest to the junction.
    
    ::
        
            >       <
            Amplicon1
                     Amplicon2
                     >       <
                     
                     ⇣

            >       <-
            Amplicon1
                     Amplicon2
                    ->       <                     
                     
    In the case of an Amplicon adjacent to a Dseqrecord object, the tail will 
    be twice as long (1*overlap) since the 
    recombining sequence is present entirely on this primer:
        
    ::
        
            Dseqrecd1
                     Amplicon1
                     >       <
                     
                     ⇣

            Dseqrecd1
                     Amplicon1
                   -->       <
    
    Note that if the sequence of DNA fragments starts or stops with an Amplicon, 
    the very first and very last prinmer will not be modified i.e. assembles are 
    always assumed to be linear. There are simple tricks around that for circular
    assemblies depicted in the last two examples below.
    
    The maxlink arguments controls the cut off length for sequences that will be
    synhtesized by adding them to primers for the adjacent fragment(s). The 
    argument list may contain short spacers (such as spacers between fusion proteins).
    

    ::

        Example 1: Linear assembly of PCR products (pydna.amplicon.Amplicon class objects) ------
        
        
        >       <         >       <
        Amplicon1         Amplicon3
                 Amplicon2         Amplicon4
                 >       <         >       <
        
                             ⇣
                             pydna.design.assembly_fragments
                             ⇣ 
        
        >       <-       ->       <-                      pydna.assembly.Assembly
        Amplicon1         Amplicon3                         
                 Amplicon2         Amplicon4     ➤  Amplicon1Amplicon2Amplicon3Amplicon4
                ->       <-       ->       <
        
        
        Example 2: Linear assembly of alternating Amplicons and other fragments
        
        
        >       <         >       <
        Amplicon1         Amplicon2
                 Dseqrecd1         Dseqrecd2
                      
                             ⇣
                             pydna.design.assembly_fragments
                             ⇣ 
                          
        >       <--     -->       <--                     pydna.assembly.Assembly
        Amplicon1         Amplicon2
                 Dseqrecd1         Dseqrecd2     ➤  Amplicon1Dseqrecd1Amplicon2Dseqrecd2
        
        
        Example 3: Linear assembly of alternating Amplicons and other fragments
        
        
        Dseqrecd1         Dseqrecd2
                 Amplicon1         Amplicon2
                 >       <       -->       <
        
                             ⇣
                     pydna.design.assembly_fragments
                             ⇣
                                                          pydna.assembly.Assembly
        Dseqrecd1         Dseqrecd2
                 Amplicon1         Amplicon2     ➤  Dseqrecd1Amplicon1Dseqrecd2Amplicon2
               -->       <--     -->       <
        
        
        Example 4: Circular assembly of alternating Amplicons and other fragments
        
                         ->       <==
        Dseqrecd1         Amplicon2
                 Amplicon1         Dseqrecd1
               -->       <-
                             ⇣
                             pydna.design.assembly_fragments
                             ⇣ 
                                                           pydna.assembly.Assembly
                         ->       <==
        Dseqrecd1         Amplicon2                    -Dseqrecd1Amplicon1Amplicon2-  
                 Amplicon1                       ➤    |                             |
               -->       <-                            -----------------------------
        
        ------ Example 5: Circular assembly of Amplicons
        
        >       <         >       <
        Amplicon1         Amplicon3
                 Amplicon2         Amplicon1
                 >       <         >       <
        
                             ⇣
                             pydna.design.assembly_fragments
                             ⇣ 
        
        >       <=       ->       <-        
        Amplicon1         Amplicon3                  
                 Amplicon2         Amplicon1
                ->       <-       +>       <
        
                             ⇣
                     make new Amplicon using the Amplicon1.template and 
                     the last fwd primer and the first rev primer.
                             ⇣
                                                           pydna.assembly.Assembly
        +>       <=       ->       <-        
         Amplicon1         Amplicon3                  -Amplicon1Amplicon2Amplicon3-
                  Amplicon2                      ➤   |                             |
                 ->       <-                          -----------------------------
        
        


    Parameters
    ----------

    f : list of :mod:`pydna.amplicon.Amplicon` and other Dseqrecord like objects
        list Amplicon and Dseqrecord object for which fusion primers should be constructed.

    overlap : int, optional
        Length of required overlap between fragments.

    maxlink : int, optional
        Maximum length of spacer sequences that may be present in f. These will be included in tails for designed primers.

    Returns
    -------
    seqs : list of :mod:`pydna.amplicon.Amplicon` and other Dseqrecord like objects :mod:`pydna.amplicon.Amplicon` objects

        ::

          [Amplicon1,
           Amplicon2, ...]


    Examples
    --------

    >>> from pydna.dseqrecord import Dseqrecord    
    >>> from pydna.design import primer_design
    >>> a=primer_design(Dseqrecord("atgactgctaacccttccttggtgttgaacaagatcgacgacatttcgttcgaaacttacgatg"))
    >>> b=primer_design(Dseqrecord("ccaaacccaccaggtaccttatgtaagtacttcaagtcgccagaagacttcttggtcaagttgcc"))
    >>> c=primer_design(Dseqrecord("tgtactggtgctgaaccttgtatcaagttgggtgttgacgccattgccccaggtggtcgtttcgtt"))
    >>> from pydna.design import assembly_fragments
    >>> # We would like a circular recombination, so the first sequence has to be repeated
    >>> fa1,fb,fc,fa2 = assembly_fragments([a,b,c,a])
    >>> # Since all fragments are Amplicons, we need to extract the rp of the 1st and fp of the last fragments.
    >>> from pydna.amplify import pcr
    >>> fa = pcr(fa2.forward_primer, fa1.reverse_primer, a)
    >>> [fa,fb,fc]
    [Amplicon(100), Amplicon(101), Amplicon(102)]
    >>> from pydna.assembly import Assembly
    >>> assemblyobj = Assembly([fa,fb,fc])
    >>> assemblyobj
    Assembly:
    Sequences........................: [100] [101] [102]
    Sequences with shared homologies.: [100] [101] [102]
    Homology limit (bp)..............: 25
    Number of overlaps...............: 3
    Nodes in graph(incl. 5' & 3')....: 5
    Only terminal overlaps...........: No
    Circular products................: [195]
    Linear products..................: [231] [231] [231] [167] [166] [165] [36] [36] [36]
    >>> assemblyobj.linear_products
    [Contig(-231), Contig(-231), Contig(-231), Contig(-167), Contig(-166), Contig(-165), Contig(-36), Contig(-36), Contig(-36)]
    >>> assemblyobj.circular_products[0].cseguid()
    'V3Mi8zilejgyoH833UbjJOtDMbc'
    >>> (a+b+c).looped().cseguid()
    'V3Mi8zilejgyoH833UbjJOtDMbc'
    >>> print(assemblyobj.circular_products[0].small_fig())
     -|100bp_PCR_prod|36
    |                 \\/
    |                 /\\
    |                 36|101bp_PCR_prod|36
    |                                   \\/
    |                                   /\\
    |                                   36|102bp_PCR_prod|36
    |                                                     \\/
    |                                                     /\\
    |                                                     36-
    |                                                        |
     --------------------------------------------------------
    >>>

    '''
    # sanity check for arguments
    nf = [item for item in f if len(item)>maxlink]
    if not all(hasattr(i[0],"template") or hasattr(i[1],"template") for i in zip(nf,nf[1:])):
        raise Exception("Every second fragment larger than maxlink has to be an Amplicon object")
    
    _module_logger.debug("### assembly fragments ###")
    _module_logger.debug("overlap     = %s", overlap)
    _module_logger.debug("max_link    = %s", maxlink)
    
    f = [_copy.copy(f) for f in f]
    
    first_fragment_length = len(f[0])
    last_fragment_length  = len(f[-1])
    
    if first_fragment_length<=maxlink:
        # first fragment should be removed and added to second fragment (new first fragment) forward primer
        f[1].forward_primer = f[0].seq.todata + f[1].forward_primer
        _module_logger.debug("first fragment removed since len(f[0]) = %s", first_fragment_length)
        f=f[1:]
    else:
        _module_logger.debug("first fragment stays since len(f[0]) = %s", first_fragment_length)

    if last_fragment_length<=maxlink:
        f[-2].reverse_primer = f[-1].seq.rc().todata + f[-2].reverse_primer
        f=f[:-1]  
        _module_logger.debug("last fragment removed since len(f[%s]) = %s", len(f), last_fragment_length)
    else:
        _module_logger.debug("last fragment stays since len(f[%s]) = %s", len(f),last_fragment_length)
        
    empty = _Dseqrecord("")    
    
    _module_logger.debug(f)
    
    _module_logger.debug("loop through fragments in groups of three:")
    
    tail_length = _math.ceil(overlap/2)
    
    for i in range(len(f)-1):

        first  = f[i] 
        secnd  = f[i+1]

        secnd_len = len(secnd)
     
        _module_logger.debug( "first = %s", str(first.seq))
        _module_logger.debug( "secnd = %s", str(secnd.seq))
        
        if secnd_len <= maxlink:  
            _module_logger.debug("secnd is smaller or equal to maxlink; should be added to primer(s)")
            third  = f[i+2]
            _module_logger.debug( "third = %s", str(third.seq))
            if hasattr(f[i], "template") and hasattr(third, "template"):
                _module_logger.debug("secnd is is flanked by amplicons, so half of secnd should be added each flanking primers")
                
                first.reverse_primer = secnd.seq.rc().todata[secnd_len//2:] + first.reverse_primer
                third.forward_primer =      secnd.seq.todata[secnd_len//2:] + third.forward_primer
                
                lnk = (third.seq.rc().todata+secnd.rc().seq.todata[:secnd_len//2])[-tail_length:]
                _module_logger.debug("1 %s", lnk)
                first.reverse_primer = lnk + first.reverse_primer
                
                lnk =  (first.seq.todata + secnd.seq.todata[:secnd_len//2])[-tail_length:]
                _module_logger.debug("2 %s", lnk)
                third.forward_primer = lnk + third.forward_primer                
                
            elif hasattr(first , "template"):
                first.reverse_primer = secnd.seq.rc().todata + first.reverse_primer
                lnk = str(third.seq[:overlap].rc())
                first.reverse_primer = lnk + first.reverse_primer
            elif hasattr(third , "template"):
               third.forward_primer = secnd.seq.todata + third.forward_primer
               lnk = str(first.seq[-overlap:])
               third.forward_primer = lnk + third.forward_primer
            secnd=empty
            f[i+2] = third
        else:                    # secnd is larger than maxlink
            if hasattr(first, "template") and hasattr(secnd, "template"):
                lnk = str(first.seq[-tail_length:])
                #_module_logger.debug("4 %s", lnk)
                secnd.forward_primer = lnk + secnd.forward_primer
                lnk = str(secnd.seq[:tail_length].rc())
                #_module_logger.debug("5 %s", lnk)
                first.reverse_primer = lnk + first.reverse_primer            
            elif hasattr(first , "template"):
                lnk = str(secnd.seq[:overlap].rc())
                #_module_logger.debug("6 %s", lnk)
                first.reverse_primer = lnk + first.reverse_primer                
            elif hasattr(secnd , "template"):
                lnk = str(first.seq[-overlap:])
                #_module_logger.debug("7 %s", lnk)
                secnd.forward_primer = lnk + secnd.forward_primer
        f[i]   = first
        f[i+1] = secnd

        
    _module_logger.debug("loop ended")
    
    f = [item for item in f if len(item)]
    
    return [_pcr(p.forward_primer, p.reverse_primer, p.template) if hasattr(p, "template") else p for p in f]

if __name__=="__main__":
    import os as _os
    cache = _os.getenv("pydna_cache", "nocache")
    _os.environ["pydna_cache"]="nocache"
    import doctest
    doctest.testmod(verbose=True, optionflags=doctest.ELLIPSIS)
    _os.environ["pydna_cache"]=cache

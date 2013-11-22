#!/usr/bin/env python
'''
Created on Oct 26, 2013
Goes through all of the files containing log entries that were not able
to be classified by course, and creates a list of the event types and
the counts for that event type. Will print out the event types in increasing
order so that the most common will be at the end.
@author: waldo
'''
import json
import glob

def buildList(fname, rdict):
    with open (fname, 'r') as fin:
        for line in fin:
            lstr = json.loads(line)
            st = lstr['event_type']
            if st not in rdict:
                rdict[st] = 1
            else:
                rdict[st] += 1
        return rdict
    
if __name__ == '__main__':
    ukdict = {}
    fname = glob.glob('*/unknown*.log')
    for n in fname:
        ukdict = buildList(fname, ukdict)
        
    s = sorted(ukdict.items(), key = lambda(k,v):(v,k))
    for i in s:
        print i

                    

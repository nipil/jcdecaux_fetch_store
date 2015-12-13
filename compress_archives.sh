#! /usr/bin/env bash

STAMP=`date +'%s'`
BASEDIR=$HOME/.jcd
BACKUPSDIR=$BASEDIR/backups
ARCHIVESDIR=$BASEDIR/archives
OUTFILE=$BACKUPSDIR/$STAMP.tar.bz2
SRCDIR=$BACKUPSDIR/$STAMP

mkdir -p $SRCDIR && \
mv $ARCHIVESDIR/*.json $SRCDIR/ -f && \
tar jcf $OUTFILE -C $BACKUPSDIR $STAMP/ && \
rm -Rf $SRCDIR/

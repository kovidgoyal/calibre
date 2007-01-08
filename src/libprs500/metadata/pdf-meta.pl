#!/usr/bin/perl
# Read/Write PDF meta data
# Based on pdf-meta from http://www.osresearch.net/wiki/index.php/Pdf-meta

use warnings;
use strict;
use PDF::API2;
use Getopt::Long;
use Data::Dumper;

my %new_info = (Creator => 'libprs500.metadata', CreationDate  => scalar( localtime ),);

GetOptions(
        "c|creator=s"           => \$new_info{Creator},
        "d|date=s"              => \$new_info{CreationDate},
        "p|producer=s"          => \$new_info{Producer},
        "a|author=s"            => \$new_info{Author},
        "s|subject=s"           => \$new_info{Subject},
        "k|keywords=s"          => \$new_info{Keywords},
        "t|title=s"             => \$new_info{Title},
) or die "Usage: (no help yet!)\n";



for my $file (@ARGV)
{
        my $pdf = PDF::API2->open( $file )
                or warn "Unable to open $file: $!\n"
                and next;

        my %info = $pdf->info;
        for my $key (keys %info)
        {
                print $key.' = """'.$info{$key}.'"""'."\n";
        }
        print "\n";

        for my $key (keys %new_info)
        {
                my $new_value = $new_info{$key};
                next unless defined $new_value;

                $info{$key} = $new_value;
        }

        $pdf->info( %info );
        $pdf->saveas( $file );
}


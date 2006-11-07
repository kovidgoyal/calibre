#! /usr/bin/perl -w

sub ST_INIT	{ 0; }
sub ST_OUT	{ 1; }
sub ST_IN	{ 2; }

$state= ST_INIT;
$count= 0;

while (<>) {
	$_= &trim($_);

	if ( />>>  URB \d+ going down  >>>/ ) {
		&dump(\%packet) if $count;
		$state= ST_OUT;
		$count++;
		%packet= (
			num	=> $count
		);
		next;
	} elsif ( /<<<  URB \d+ coming back  <<</ ) {
		$state= ST_IN;
		next;
	} elsif ( $state == ST_INIT ) {
		next;
	}

	if ( /^-- URB_FUNCTION_CONTROL_TRANSFER/ ) {
		$packet{pipe}= 'C';
	} elsif ( /^-- URB_FUNCTION_BULK_OR_INTERRUPT_TRANSFER/ ) {
		$packet{pipe}= 'B';
	} elsif ( /^\s+([0-9a-f]{8}:)\s+(.*)/ ) {
		my ($offset)= $1;
		my ($data) = $2;
		my ($dline);

		unless ( exists $packet{direction} ) {
			$packet{direction}= ( $state == ST_IN ) ? '<' : '>';
			$packet{data}= [];
		}

		#$_= <>;
		#$_= &trim($_);

		$dline= sprintf("%s %s", $offset, &ascii_rep($data));

		push (@{$packet{data}}, $dline);
	} elsif ( /^\s+SetupPacket/ ) {
	  $_ = <>;
	  $packet{setup}= (split(/:\s+/))[1];
	}
}

&dump(\%packet) if $count;

0;

sub dump {
	my ($href)= @_;

	printf("%06d\t%s", $href->{num}, $href->{pipe});
	if ( $href->{pipe} eq 'C' ) {
		printf("S            %s", $href->{setup});
		if ( exists $href->{direction} ) {
			print "\n";
			$line= shift(@{$href->{data}});
			printf("\tC%s  %s", $href->{direction}, $line);
		}
	} elsif ( $href->{pipe} eq 'B' ) {
		if ( exists $href->{direction} ) {
			$line= shift(@{$href->{data}});
			printf("%s  %s", $href->{direction}, $line);
		}
	} else {
		warn "unknown pipe";
	}

	foreach $line (@{$href->{data}}) {
		printf("\t    %s", $line);
	}

	print "\n";
}

sub trim {
	my ($line)= @_;

	$line=~ s///g;
	$line=~ s/^\d+\s+\d+\.\d+\s+//;

	return $line;
}

sub ascii_rep {
	my (@hexdata)= split(/\s+/, $_[0]);
	my ($i)= 0;
	my ($compact, $width);
	my ($ascii, $byte);

	foreach $byte (@hexdata) {
		my ($dec)= hex($byte);
		my ($abyte);

		$compact.= $byte;
		$compact.= ' ' if ($i%2);
		$i++;

		$ascii.= ( $dec > 31 && $dec < 127 ) ? sprintf("%c", $dec) :
			'.';
	}

	$width= 40-length($compact);
	return sprintf("%s%s %s\n", $compact, ' 'x${width}, $ascii);
}


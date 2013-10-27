#!/usr/bin/perl --

use strict;
use Net::Twitter::Lite::WithAPIv1_1;
use YAML::Tiny;
use Encode;
use Data::Dumper;
use YAML::Tiny;
use Scalar::Util 'blessed';
use Jcode;
use LWP::Simple;
use open IN  => ":utf8";
use Time::Piece ();
use Time::HiRes;  #処理時間の計算
use CGI;
my $q = new CGI;
$Win32::OLE::Warn = 3;

sub func;
sub related;
sub precision;
sub row_precision; #pos/negでない判定

my $tmp = (YAML::Tiny->read('config.yaml'));
my $config = $tmp->[0];
my $yahoo_id = "yahooid";
my $in;                                                
my $t = Time::Piece::localtime(time-50400); #５時間前
substr($t,19,0," +0000");	#5時間前 
my $search_time = $t;
my $year = substr($search_time,26,4);
my $day = substr($search_time,8,2);
substr($search_time,25,5,"");
substr($search_time,8,2,"");
substr($search_time,3,0,", $day");
substr($search_time,12,0,"$year");

my %relate=();	#関連語
my %user_count=();	#とりあえず量的ポイントのランキングをハッシュにて
my %tweet_point = ();	#各ツイートのポイント ポジネガ判定に用いる
my %tweet_user = ();
my %row_relate = ();
my %tweet_text = ();
my %image_url = ();
my %user_retweet = ();	#各ユーザがリツイートされた数
my %user_sum = ();	#userのsum値
my %retweet_id = ();	#リツイートとしてカウントしたツイートのID
my %key_count = ();	#キーワードをつぶやいた数
my $dic;	#辞書
my @relate_dic;	#関連語辞書
my %hashtag;
my $in_number = 0; #検索語の出現回数
my $start_time = Time::HiRes::time; 

$" = "|";
my $nt = Net::Twitter::Lite::WithAPIv1_1->new(
	  consumer_key	=> 'consumer_key',
	  consumer_secret => 'consumer_secret',
);
$nt->access_token('access_token');
$nt->access_token_secret('access_token_secret');

print "Content-type: text/html\n\n";
print "<HTML>";
print "<HEAD>";

eval {
$in = $q->param('data1');
&Jcode::convert(\$in,'unicode');
$in =~ s/\n|\r//sg;	#改行を取り除く
$in =~ tr/　/ /;	#全角スペースを半角スペースに
push(@relate_dic,$in);
$relate{$in} = 1;	#検索語自体の重み付けは1 (仮)

# 関連語辞書の読み込み
open(IN,"<../dictionary.txt");
while(my $line=<IN>){
	my $uni_line = Jcode->new($line,"utf8")->unicode;
	$dic = $dic.$uni_line.",";
}
$dic =~ s/\n|\r//sg;

my $all_text;
my $search_text; #検索結果のテキスト
my $all_tmp;
my $search_tmp; #検索結果用のtmp
my $max_id = 0;
my $r;
for(my $i=1;$i<11;$i++){
	if($max_id != 0){
		$r = $nt->search({q=>$in,count=>100, max_id => $max_id, lang => 'ja'});
	}else{
		$r = $nt->search({q=>$in,count=>100, lang => 'ja'});
	}
	
	STEP: for my $res (@{$r->{statuses}}) {
		$max_id = $res->{id_str};
		next if ($res->{text} =~ /\A@/s || exists($tweet_point{$res->{id}}));	#リプライと既出ツイートは削除
		$res->{text} =~ s/@.*|RT.*//s;	#リプライとRT以後を消す

		if($res->{text} !~ /$in/s){
			next STEP;	#リプライ引用下に検索ワードが入ってきているのであれば
		}
		$key_count{$res->{user}->{screen_name}}++;
		$tweet_point{$res->{id}} = 1;
		$tweet_text{$res->{id}} = $res->{text};
		$tweet_user{$res->{id}} = $res->{user}->{screen_name};
		$in_number++;
		
		$search_tmp = $search_text.$res->{text}; 
		
		if(&func($search_tmp,$search_text,0)==1){
			$search_text = $res->{text};
		}else{
			$search_text = $search_tmp;
		}   
	}
}

#最後に余った(900文字に満たない)$textを形態素解析に
&func(0,$search_text,1);
};

#形態素解析
sub func{
	my $tmp = $_[0];
	my $text = $_[1];
	my $last = $_[2];	#最後かどうか
	my @row;

	if(length($tmp) > 900 || $last == 1){ #900文字を超えたらAPIに通す
		$text =~ tr/[\n\r\&\#\%]//d;

		$text =~ s/$in/ /sg;	#あとで配列の評価をもっと簡単にできるかも

		#$text = jcode($text)->tr('０-９ ａ-ｗ Ａ-Ｗ', '0-9a-wA-W');	#全角を半角に
		$text =~ tr/０-９ａ-ｗＡ-Ｗ/0-9a-wA-W/;
		my $mol = get("http://jlp.yahooapis.jp/MAService/V1/parse?appid=$yahoo_id&results=uniq&filter=9&sentence=$text"); #molは形態素
		if(defined($mol)){
				while ($mol =~ /<count>(.*?)<\/count>.*?<surface>(.*?)<\/surface>.*?<pos>.*?<\/pos>/sg){
				#	$dbh->do("insert into words (surface,count) values ('$2','$1');");

					$row_relate{$2} += $1;
				}
		}
	return 1;
	}else{ return 0;}
}

if ( my $err = $@ ) {
    die $@ unless blessed $err && $err->isa('Net::Twitter::Error');
    warn
        "HTTP Response Code: ", $err->code, "<br>",
        "HTTP Message......: ", $err->message, "<br>",
        "Twitter error.....: ", $err->error,   "<br>";
}

my $relate_count = 0;	#関連語のカウント
my $_relate_dic = join(",",@relate_dic);
# 形態素解析の結果の出力
foreach my $key (sort { $row_relate{$b} <=> $row_relate{$a} } keys %row_relate){
	# 各行のフェッチ
	$key = Jcode->new($key,"utf8")->unicode;	#unicodeに変換

	if( $dic !~ /$key,/ && $key !~ /@relate_dic/ && $_relate_dic !~ /$key/){	#頻出辞書にも含まれず逆もしかり
								#検索ワード自体にも含まれない単語であれば
								#row[0] は、$dicの各文字と完全一致させるための工夫
		push(@relate_dic,$key);
		$_relate_dic = $_relate_dic.",".$key;
		&related($key,$row_relate{$key});
		$relate_count++;
		last if($relate_count > 15);
	}
}

#userごとのpositive数計算
foreach my $key (sort { $tweet_point{$b} <=> $tweet_point{$a} } keys %tweet_point){
	last if($tweet_point{$key} == 0);	#閾値0.3
	$user_count{$tweet_user{$key}}++;
	$user_sum{$tweet_user{$key}} += $tweet_point{$key};
}

my $user_count = 0;
my %user_rank = ();
# 各行のフェッチ
foreach my $key (sort { $user_count{$b} <=> $user_count{$a} } keys %user_count){
	my $tweet_count; #リプライを除いたツイート数
	my $url = 0;
	my $retweet = 0;
	my $positive = 0;
	my $sum_point = 0;
	my $retweet = 0;
  	($tweet_count,$url,$positive,$tweet_count,$sum_point,$retweet) = &precision($key);
	if($tweet_count == 0){
		next;
	}
	$user_rank{$key} = $positive * ($sum_point/$tweet_count);
	$user_count++;
	last if($user_count > 50);
}                                                                        

sub related{
	my $cosine;
	my $word = $_[0];
	my $number = $_[1];
	my $tmp_count = 0;
	my $total = 0;
	my %tmp_users = ();
	my %tmp_id_memo = ();
	my @tmp_id = ();
	my $max_id = 0;
	my $r;
	
	&Jcode::convert(\$word,'unicode');
	for(my $i=1;$i<4;$i++){     	
		if($max_id != 0){
			$r = $nt->search({q=>$word,count=>100, max_id => $max_id, 'lang' => 'ja'});
		}else{
			$r = $nt->search({q=>$word,count=>100, 'lang' => 'ja'});
		}

		for my $res (@{$r->{statuses}}){
			$max_id = $res->{id_str};
			next if(exists($tmp_id_memo{$res->{id}}));	#最初の文字がRTだったら  (ここではRT完全無視という前提で 
						#or 既出ツイートとばし
			if($res->{text} =~ /\ART.*?\@(.*?)( |:)/){
				next if(exists($retweet_id{$res->{id}}));
				if(exists($user_retweet{$1})){
					$user_retweet{$1}++;
				}
				else{
					$user_retweet{$1} = 1;
				}
				$retweet_id{$res->{id}} = 1;
				next;
			}
			$tmp_id_memo{$res->{id}} = 1;
		
			$res->{text} =~ s/@.*|RT.*//s;	#リプライとRT以後を消す
			next if($res->{text} !~ /$word/s);	#リプライ引用下に検索ワードが入ってきているのであればそれはtotalにもtmp_countにも加算しない
			push(@tmp_id,$res->{id});	#ツイートidを保存
			$tweet_user{$res->{id}} = $res->{user}->{screen_name};
			$tweet_text{$res->{id}} = $res->{text};
			if($res->{text} =~ /$in/s){
				$tmp_count++;
			}	

			$total++;

		}
	}

	if($total != 0){
		my $cal_2 = $tmp_count/$total; #分母                     
		if($cal_2 != 0){
			my $cal_1 = $number/$in_number; #分子
			my $cal = $cal_1/$cal_2;
			my $b_number = $cal * $in_number;
			$cosine = $number / sqrt ($in_number*$b_number);
		}else{
			$cosine = 0;
		}	
		if($cosine > 0){                           
			$relate{$word} = $cosine;   
			foreach my $id (@tmp_id){
				$tweet_point{$id} += $cosine;
			}
		}
	}

}

sub precision{
	my $user = $_[0];
	my $count = 0; 	#全カウント
	my $positive = 0;	#関連ツイートカウント
	my $point;
	my $url_count = 0;
	my $sum_point = 0;
	my $retweet = 0;
	my $check = 0;	#ぼっと対処
	my $used = "";
	my $used_count = 0;
	my $first = 1;
	&Jcode::convert(\$user,'unicode');
	my $user_timeline = $nt->user_timeline({screen_name=>$user,count=>50}); 
	for my $res(@$user_timeline){
		
		if($first == 1){
			$image_url{$user} = $res->{user}->{profile_image_url};;
			$first = 0;
		}
		$res->{text} =~ s/(#|＃).*?( |\r)//sg; #ハッシュタグ消し
		$res->{text} =~ s/(#|＃).*$//s;
		if($res->{text} =~ /\A@/){
			$check = 1;
			next;
		}	#リプライだったら
		
		if($res->{text} !~ /http/s){	#URLなしなら
			$check = 1;
		}
		$res->{text} =~ s/@.*|RT.*//s;	#リプライとRT以後を消す
			
		
		$count++;		
		$point = 0;
		
		foreach my $key (keys(%relate)){
			next if($relate{$key} == 0);
			if($res->{text} =~ /$key/s){
				if($used !~ /$key/){
					$used_count++;
					if($key eq $in){	#あとで　2語以上対応
						$used_count++;
					}
					$used = $used.",".$key;
				}
				$point += $relate{$key};
			}
		}
		
		if($point > 0){
			$positive++;
		}
		$sum_point += $point;
		$retweet += $res->{retweet_count};

	}

	if($count != 0){
		if($count > 10 && $check == 0){
			$positive = 0;
		}
		elsif($used_count < 2){
			$positive = 0;
		}
		return ($count,$url_count,$positive,$count,$sum_point,$retweet);
	}
	else{
		return (0,0,0,0,0);
	}
}

delete($relate{$in});


print "<LINK href=\"../main.css\" rel=\"stylesheet\" type=\"text/css\">";
print<<'EOF';
<!--Load the AJAX API-->
    <script type="text/javascript" src="https://www.google.com/jsapi"></script>
    <script type="text/javascript">
    
      // Load the Visualization API and the piechart package.
      google.load('visualization', '1.0', {'packages':['corechart']});
      
      // Set a callback to run when the Google Visualization API is loaded.
      google.setOnLoadCallback(drawChart);

      // Callback that creates and populates a data table, 
      // instantiates the pie chart, passes in the data and
      // draws it.
      function drawChart() {

      // Create the data table.
      var data = new google.visualization.DataTable();
      data.addColumn('string', 'Word');
      data.addColumn('number', 'Number');
      data.addRows([
EOF

my $_num = keys(%relate);
my $count = 0;
foreach my $key(sort { $relate{$b} <=> $relate{$a} } keys %relate){
	$count++;
    print "\n[\'$key\', $relate{$key}]";
	if($count != $_num){
		print ",";
	}
}
print "\n]);\n";

my $title = "「」の関連語";
&Jcode::convert(\$title,'unicode');
substr($title, 1, 0) = $in;
print "var options = {\'title\':\'$title\',";
print<<'EOF';
                     'width':800,
                     'height':600,
					  backgroundColor: { fill:'transparent' }
					};

      // Instantiate and draw our chart, passing in some options.
      var chart = new google.visualization.PieChart(document.getElementById('chart_div'));
      chart.draw(data, options);
EOF

print<<'EOF';
      var person = new google.visualization.DataTable();
      person.addColumn('string', 'twitterID');
      person.addColumn('number', '推薦度');
      person.addRows([
EOF

$count = 0;
foreach my $key(sort { $user_rank{$b} <=> $user_rank{$a} } keys %user_rank){
	$count++;
    print "\n[\'\@$key\', $user_rank{$key}]";
	if($count != 5){
		print ",";
	}
	else{
		last;
	}
}
print "\n]);\n";

print<<'EOF';
	　var per_options = {'title':'推薦レポータ',
                     'width':800,
                     'height':600,
					  backgroundColor: { fill:'transparent' }
					};

      // Instantiate and draw our chart, passing in some options.
      var persons = new google.visualization.BarChart(document.getElementById('person_div'));
      persons.draw(person, per_options);
    }
    </script>
EOF
print "<meta http-equiv='Content-Type' content='text/html; charset=unicode'>";
print "</HEAD>";
print "<BODY>";
print "<center><img src=\"../logo.png\"></center><p><br>";
print "<div id=\"chart_div\" style=\"width:800; height:600\"></div>";
print "<div id=\"person_div\" style=\"width:800; height:600\"></div>";
print "<div id=\"table\">";
$count = 0;
foreach my $key(sort { $user_rank{$b} <=> $user_rank{$a} } keys %user_rank){
	$count++;
	print '<div class="row"><div class="u1"><a href="';
	print "https://twitter.com/$key";
	print '" target="_blank">';
	print '<img src = "';
    print $image_url{$key};
	print '"></a></div></div>';
	if($count == 5){
		last;
	}
}
print '</div>';
print "<div id=\"result_tp\">";
print "<HR size=\"4\" color=\"010101\">";
print "&copy; TAJI and USHIAMA lab. All Rights Reserved.";
print "</div>";
print "</BODY>";
print "</HTML>";


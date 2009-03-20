#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Keep track of donations to calibre.
'''
import sys, cStringIO, textwrap, traceback, re, os, time
from datetime import date, timedelta
from math import sqrt
os.environ['HOME'] = '/tmp'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


import cherrypy
from lxml import etree

def range_for_month(year, month):
    ty, tm = date.today().year, date.today().month
    min = max = date(year=year, month=month, day=1)
    x = date.today().day if ty == year and tm == month else 31
    while x > 1:
        try:
            max = min.replace(day=x)
            break
        except ValueError:
            x -= 1
    return min, max

def range_for_year(year):
    return date(year=year, month=1, day=1), date(year=year, month=12, day=31)
    

def rationalize_country(country):
    if re.match('(?i)(US|USA|America)', country):
        country = 'USA'
    elif re.match('(?i)(UK|Britain|england)', country):
        country = 'UK'
    elif re.match('(?i)italy', country):
        country = 'Italy'
    elif re.match('(?i)germany', country):
        country = 'Germany'
    elif re.match('(?i)france', country):
        country = 'France'
    elif re.match('(?i)ireland', country):
        country = 'Ireland'
    elif re.match('(?i)norway', country):
        country = 'Norway'
    elif re.match('(?i)canada', country):
        country = 'Canada'
    elif re.match(r'(?i)new\s*zealand', country):
        country = 'New Zealand'
    elif re.match('(?i)jamaica', country):
        country = 'Jamaica'
    elif re.match('(?i)australia', country):
        country = 'Australia'
    elif re.match('(?i)Netherlands', country):
        country = 'Netherlands'
    elif re.match('(?i)spain', country):
        country = 'Spain'
    elif re.match('(?i)colombia', country):
        country = 'Colombia'
    return country

class Record(object):
    
    def __init__(self, email, country, amount, date, name):
        self.email = email
        self.country = country
        self.amount = amount
        self.date = date
        self.name = name
        
    def __str__(self):
        return '<donation email="%s" country="%s" amount="%.2f" date="%s" %s />'%\
        (self.email, self.country, self.amount, self.date.isoformat(), 'name="%s"'%self.name if self.name else '')

class Country(list):

    def __init__(self, name):
        list.__init__(self)
        self.name = name
        self.total = 0.
        self.percent = 0.

    def append(self, r):
        self.total += r.amount
        list.append(self, r)

    def __str__(self):
        return self.name + ': %.2f%%'%self.percent
    
    def __cmp__(self, other):
        return cmp(self.total, other.total)


class Stats:

    def get_deviation(self, amounts):
        l = float(len(amounts))
        if l == 0:
            return 0
        mean = sum(amounts)/l
        return sqrt( sum([i**2 for i in amounts])/l - mean**2  )

    def __init__(self, records, start, end):
        self.total = sum([r.amount for r in records])
        self.days = {}
        l, rg = date.max, date.min
        self.totals = []
        for r in records:
            self.totals.append(r.amount)
            l, rg = min(l, r.date), max(rg, r.date)
            if r.date not in self.days.keys():
                self.days[r.date] = []
            self.days[r.date].append(r)
            
        self.min, self.max = start, end
        self.period = (self.max - self.min) + timedelta(days=1)
        daily_totals = []
        day = self.min
        while day <= self.max:
            x = self.days.get(day, [])
            daily_totals.append(sum([y.amount for y in x]))
            day += timedelta(days=1)
        self.daily_average = self.total/self.period.days
        self.daily_deviation = self.get_deviation(daily_totals)
        self.average = self.total/len(records) if len(records) else 0.
        self.average_deviation = self.get_deviation(self.totals)
        self.countries = {}
        self.daily_totals = daily_totals
        for r in records:
            if r.country not in self.countries.keys():
                self.countries[r.country] = Country(r.country)
            self.countries[r.country].append(r)
        for country in self.countries.values():
            country.percent = (100 * country.total/self.total) if self.total else 0.
        
    def __str__(self):
        buf = cStringIO.StringIO()
        print >>buf, '\tTotal: %.2f'%self.total
        print >>buf, '\tDaily Average: %.2f'%self.daily_average
        print >>buf, '\tAverage contribution: %.2f'%self.average
        print >>buf, '\tCountry breakup:'
        for c in self.countries.values():
            print >>buf, '\t\t', c
        return buf.getvalue()
    
    def to_html(self, num_of_countries=sys.maxint):
        countries = sorted(self.countries.values(), cmp=cmp, reverse=True)[:num_of_countries]
        crows = ['<tr><td>%s</td><td class="country_percent">%.2f %%</td></tr>'%(c.name, c.percent) for c in countries]
        ctable = '<table>\n<tr><th>Country</th><th>Contribution</th></tr>\n%s</table>'%('\n'.join(crows))
        if num_of_countries < sys.maxint:
            ctable = '<p>Top %d countries</p>'%num_of_countries + ctable
        return textwrap.dedent('''
        <div class="stats">
            <p style="font-weight: bold">Donations in %(period)d days [%(min)s &mdash; %(max)s]:</p>
            <table style="border-left: 4em">
                <tr><td>Total</td><td class="money">$%(total).2f (%(num)d)</td></tr>
                <tr><td>Daily average</td><td class="money">$%(da).2f &plusmn; %(dd).2f</td></tr>
                <tr><td>Average contribution</td><td class="money">$%(ac).2f &plusmn; %(ad).2f</td></tr>
                <tr><td>Donors per day</td><td class="money">%(dpd).2f</td></tr>
            </table>
            <br />
            %(ctable)s
        </div>
        ''')%dict(total=self.total, da=self.daily_average, ac=self.average, 
                  ctable=ctable, period=self.period.days, num=len(self.totals),
                  dd=self.daily_deviation, ad=self.average_deviation, 
                  dpd=len(self.totals)/float(self.period.days), 
                  min=self.min.isoformat(), max=self.max.isoformat())
        

def expose(func):
    
    def do(self, *args, **kwargs):
        dict.update(cherrypy.response.headers, {'Server':'Donations_server/1.0'})
        return func(self, *args, **kwargs)
    
    return cherrypy.expose(do)

class Server(object):
    
    TRENDS = '/tmp/donations_trend.png'
    MONTH_TRENDS = '/tmp/donations_month_trend.png'
    
    def __init__(self, apache=False, root='/', data_file='/tmp/donations.xml'):
        self.apache = apache
        self.document_root = root
        self.data_file = data_file
        self.read_records()
    
    def calculate_month_trend(self, days=31):
        stats = self.get_slice(date.today()-timedelta(days=days-1), date.today())
        fig = plt.figure(2, (10, 4), 96)#, facecolor, edgecolor, frameon, FigureClass)
        fig.clear()
        ax = fig.add_subplot(111)
        x = list(range(days-1, -1, -1))
        y = stats.daily_totals
        ax.plot(x, y)#, align='center', width=20, color='g')
        ax.set_xlabel('Days ago')
        ax.set_ylabel('Income ($)')
        ax.hlines([stats.daily_average], 0, days-1)
        ax.hlines([stats.daily_average+stats.daily_deviation,
                   stats.daily_average-stats.daily_deviation], 0, days-1,
                   linestyle=':',color='r')
        ax.set_xlim([0, days-1])
        text = u'''\
Total: $%(total).2f
Daily average: $%(da).2f \u00b1 %(dd).2f
Average contribution: $%(ac).2f \u00b1 %(ad).2f
Donors per day: %(dpd).2f
        '''%dict(total=stats.total, da=stats.daily_average, 
                 dd=stats.daily_deviation, ac=stats.average,
                 ad=stats.average_deviation,
                 dpd=len(stats.totals)/float(stats.period.days),
             )
        text = ax.annotate(text, (0.5, 0.65), textcoords='axes fraction')
        fig.savefig(self.MONTH_TRENDS)
    
    def calculate_trend(self):
        def months(start, end):
            pos = range_for_month(start.year, start.month)[0]
            while pos <= end:
                yield (pos.year, pos.month)
                if pos.month == 12:
                    pos = pos.replace(year = pos.year+1)
                    pos = pos.replace(month = 1)
                else:
                    pos = pos.replace(month = pos.month + 1)
        _months = list(months(self.earliest, self.latest))[:-1][-12:]
        _months = [range_for_month(*m) for m in _months]
        _months = [self.get_slice(*m) for m in _months]
        x = [m.min for m in _months]
        y = [m.total for m in _months]
        ml   = mdates.MonthLocator() # every month
        fig = plt.figure(1, (8, 4), 96)#, facecolor, edgecolor, frameon, FigureClass)
        fig.clear()
        ax = fig.add_subplot(111)
        average = sum(y)/len(y)
        ax.bar(x, y, align='center', width=20, color='g')
        ax.hlines([average], x[0], x[-1])
        ax.xaxis.set_major_locator(ml)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
        ax.set_xlim(_months[0].min-timedelta(days=15), _months[-1].min+timedelta(days=15))
        ax.set_xlabel('Month')
        ax.set_ylabel('Income ($)')
        fig.autofmt_xdate()
        fig.savefig(self.TRENDS)
        #plt.show()

        
    def read_records(self):
        self.tree = etree.parse(self.data_file)
        self.last_read_time = time.time()
        self.root = self.tree.getroot()
        self.records = []
        min_date, max_date = date.today(), date.fromordinal(1)
        for x in self.root.xpath('//donation'):
            d = list(map(int, x.get('date').split('-')))
            d = date(*d)
            self.records.append(Record(x.get('email'), x.get('country'), float(x.get('amount')), d, x.get('name')))
            min_date = min(min_date, d)
            max_date = max(max_date, d)
        self.earliest, self.latest = min_date, max_date
        self.calculate_trend()
        self.calculate_month_trend()
            
    def get_slice(self, start_date, end_date):
        stats = Stats([r for r in self.records if r.date >= start_date and r.date <= end_date],
                        start_date, end_date)
        return stats
    
    def month(self, year, month):
        return self.get_slice(*range_for_month(year, month))
    
    def year(self, year):
        return self.get_slice(*range_for_year(year))
    
    def range_to_date(self, raw):
        return date(*map(int, raw.split('-')))
    
    def build_page(self, period_type, data):
        if os.stat(self.data_file).st_mtime >= self.last_read_time:
            self.read_records()
        month = date.today().month
        year = date.today().year
        mm = data[1] if period_type == 'month' else month
        my = data[0] if period_type == 'month' else year
        yy = data if period_type == 'year' else year
        rl = data[0] if period_type == 'range' else ''
        rr = data[1] if period_type == 'range' else ''
        
        def build_month_list(current):
            months = []
            for i in range(1, 13):
                month = date(2000, i, 1).strftime('%b')
                sel = 'selected="selected"' if i == current else ''
                months.append('<option value="%d" %s>%s</option>'%(i, sel, month))
            return months
        
        def build_year_list(current):
            all_years = sorted(range(self.earliest.year, self.latest.year+1, 1))
            if current not in all_years:
                current = all_years[0]
            years = []
            for year in all_years:
                sel = 'selected="selected"' if year == current else ''
                years.append('<option value="%d" %s>%d</option>'%(year, sel, year))
            return years
        
        mmlist = '<select name="month_month">\n%s</select>'%('\n'.join(build_month_list(mm)))
        mylist = '<select name="month_year">\n%s</select>'%('\n'.join(build_year_list(my)))
        yylist = '<select name="year_year">\n%s</select>'%('\n'.join(build_year_list(yy)))
        
        if period_type == 'month':
            range_stats = range_for_month(my, mm)
        elif period_type == 'year':
            range_stats = range_for_year(yy)
        else:
            try:
                range_stats = list(map(self.range_to_date, (rl, rr)))
                err = None
            except:
                range_stats = None
                err = traceback.format_exc()
        if range_stats is None:
            range_stats = '<pre>Invalid input:\n%s</pre>'%err
        else:
            range_stats = self.get_slice(*range_stats).to_html(num_of_countries=10)
        
        today = self.get_slice(date.today(), date.today())
        
        return textwrap.dedent('''\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml" version="XHTML 1.1" xml:lang="en">
            <head>
                <title>Calibre donations</title>
                <link rel="icon" href="http://calibre.kovidgoyal.net/chrome/site/favicon.ico" type="image/x-icon" />
                <style type="text/css">
                    body { background-color: white }
                    .country_percent { text-align: right; font-family: monospace; }
                    .money { text-align: right; font-family: monospace; padding-left:2em;}
                    .period_box { padding-left: 60px; border-bottom: 10px; }
                    #banner {font-size: xx-large; font-family: cursive; text-align: center}
                    #stats_container td { vertical-align: top }
                </style>
                <script type="text/javascript">
                    String.prototype.trim = function() {
                        return this.replace(/^\s+|\s+$/g,"");
                    }

                    function test_date(date) {
                        var valid_format = /\d{4}-\d{1,2}-\d{1,2}/;
                        if (!valid_format.test(date)) return false;
                        var yearfield  = date.split('-')[0];
                        var monthfield = date.split('-')[1];
                        var dayfield   = date.split('-')[2];
                        var dayobj     = new Date(yearfield, monthfield-1, dayfield)
                        if ((dayobj.getMonth()+1!=monthfield)||(dayobj.getDate()!=dayfield)||(dayobj.getFullYear()!=yearfield)) return false;
                        return true;
                    }
                
                    function check_period_form(form) {
                        if (form.period_type[2].checked) {
                            if (!test_date(form.range_left.value)) {
                                form.range_left.focus();
                                alert("Left Range date invalid!");
                                return false;
                            }
                            if (!test_date(form.range_right.value)) {
                                form.range_right.focus();
                                alert("Right Range date invalid!");
                                return false;
                            }
                        }
                        return true;
                    }
                    
                    function is_empty(val) {
                        return val.trim().length == 0
                    }
                    
                    function check_add_form(form) {
                        var test_amount = /[\.0-9]+/;
                        if (is_empty(form.email.value)) {
                            form.email.focus();
                            alert("Email must be filled!");
                            return false;
                        }
                        if (is_empty(form.country.value)) {
                            form.country.focus();
                            alert("Country must be filled!");
                            return false;
                        }
                        if (!test_amount.test(form.amount.value)) {
                            form.amount.focus();
                            alert("Amount " + form.amount.value + " is not a valid number!");
                            return false;
                        }
                        if (!test_date(form.date.value)) {
                            form.date.focus();
                            alert("Date " + form.date.value +" is invalid!");
                            return false;
                        }
                        return true;
                    } 
                    
                    function rationalize_periods() {
                        var form = document.forms[0];
                        var disabled = !form.period_type[0].checked;
                        form.month_month.disabled = disabled;
                        form.month_year.disabled  = disabled;
                        disabled = !form.period_type[1].checked;
                        form.year_year.disabled = disabled;
                        disabled = !form.period_type[2].checked;
                        form.range_left.disabled = disabled;
                        form.range_right.disabled = disabled;
                    }
                </script>
            </head>
            <body onload="rationalize_periods()">
                <table id="banner" style="width: 100%%">
                    <tr>
                        <td style="text-align:left; width:150px"><a style="border:0pt" href="http://calibre.kovidgoyal.net"><img style="vertical-align: middle;border:0pt" alt="calibre" src="http://calibre.kovidgoyal.net/chrome/site/calibre_banner.png" /></a></td>
                        <td>Calibre donations</td>
                    </tr>
                </table>
                <hr />
                <table id="stats_container" style="width:100%%">
                    <tr>
                        <td id="left">
                            <h3>Donations to date</h3>
                            %(todate)s
                        </td>
                
                        <td id="right">
                            <h3>Donations in period</h3>
                            <fieldset>
                                <legend>Choose a period</legend>
                                <form method="post" action="%(root)sshow" onsubmit="return check_period_form(this);">
                                    <input type="radio" name="period_type" value="month" %(mc)s onclick="rationalize_periods()"/>
                                        Month:&nbsp;%(month_month)s&nbsp;%(month_year)s
                                    <br /><br />
                                    <input type="radio" name="period_type" value="year" %(yc)s onclick="rationalize_periods()" />
                                        Year:&nbsp;%(year_year)s
                                    <br /><br />
                                    <input type="radio" name="period_type" value="range" %(rc)s onclick="rationalize_periods()" />
                                        Range (YYYY-MM-DD):&nbsp;<input size="10" maxlength="10" type="text" name="range_left" value="%(rl)s" />&nbsp;to&nbsp;<input size="10" maxlength="10" type="text" name="range_right" value="%(rr)s"/>
                                    <br /><br />
                                    <input type="submit" value="Update" />
                                </form>
                            </fieldset>
                            <b>Donations today: $%(today).2f</b><br />
                            %(range_stats)s
                        </td>
                    </tr>
                </table>
                <hr />
                <div style="text-align:center">
                    <h3>Income trends for the last year</h3>
                    <img src="%(root)strend.png" alt="Income trends" />
                    <h3>Income trends for the last 31 days</h3>
                    <img src="%(root)smonth_trend.png" alt="Month income trend" />
                </div>
            </body>
        </html>
        ''')%dict(
                  todate=self.get_slice(self.earliest, self.latest).to_html(),
                  mc = 'checked="checked"' if period_type=="month" else '',
                  yc = 'checked="checked"' if period_type=="year" else '',
                  rc = 'checked="checked"' if period_type=="range" else '',
                  month_month=mmlist, month_year=mylist, year_year=yylist,
                  rl=rl, rr=rr, range_stats=range_stats, root=self.document_root,
                  today=today.total
                  )
    
    @expose
    def index(self):
        month = date.today().month
        year = date.today().year
        cherrypy.response.headers['Content-Type'] = 'application/xhtml+xml'
        return self.build_page('month', (year, month))
    
    @expose
    def trend_png(self):
        cherrypy.response.headers['Content-Type'] = 'image/png'
        return open(self.TRENDS, 'rb').read()
    
    @expose
    def month_trend_png(self):
        cherrypy.response.headers['Content-Type'] = 'image/png'
        return open(self.MONTH_TRENDS, 'rb').read()
    
    @expose
    def show(self, period_type='month', month_month='', month_year='', 
             year_year='', range_left='', range_right=''):
        if period_type == 'month':
            mm = int(month_month) if month_month else date.today().month
            my = int(month_year) if month_year else date.today().year
            data = (my, mm)
        elif period_type == 'year':
            data = int(year_year) if year_year else date.today().year
        else:
            data = (range_left, range_right)
        cherrypy.response.headers['Content-Type'] = 'application/xhtml+xml'
        return self.build_page(period_type, data)
    
def config():
    config = {
            'global': {
                'tools.gzip.on'        : True,
                'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/xml', 'text/javascript', 'text/css', 'application/xhtml+xml'],
            }
    }
    return config

def apache_start():
    cherrypy.config.update({
        'log.screen'      : False,
        #'log.error_file'  : '/tmp/donations.log',
        'environment'     : 'production',
        'show_tracebacks' : False,
        })
    cherrypy.tree.mount(Server(apache=True, root='/donations/', data_file='/var/www/calibre.kovidgoyal.net/donations.xml'), 
                        '/donations', config=config())
    

def main(args=sys.argv):
    server = Server()
    cherrypy.quickstart(server, config=config())
    return 0

if __name__ == '__main__':
    sys.exit(main())

# This is a general purpose library for scraping any Swift LG planning site.
# PlanningUtils.py library, taken from PlanningAlerts.com code

__auth__ = None

import re

#import scraperwiki.datastore

date_format = "%d/%m/%Y"

def fixNewlines(text):
    # This can be used to sort out windows newlines
    return text.replace("\r\n","\n")

# So what can a postcode look like then?
# This list of formats comes from http://www.mailsorttechnical.com/frequentlyaskedquestions.cfm
#AN NAA      M1 1AA
#ANN NAA     M60 1NW
#AAN NAA     CR2 6XH
#AANN NAA     DN55 1PT
#ANA NAA     W1A 1HP
#AANA NAA     EC1A 1BB

postcode_regex = re.compile("[A-Z][A-Z]?\d(\d|[A-Z])? ?\d[A-Z][A-Z]")

def getPostcodeFromText(text, default_postcode="No Postcode"):
    """This function takes a piece of text and returns the first
    bit of it that looks like a postcode."""

    postcode_match = postcode_regex.search(text)

    return postcode_match.group() if postcode_match else default_postcode


class PlanningAuthorityResults:
    """This class represents a set of results of a planning search.

       This should probably be separated out so that it can be used for
       authorities other than Cherwell.
       """

    def __init__(self, authority_name, authority_short_name):
        self.authority_name = authority_name
        self.authority_short_name = authority_short_name
    
        # this will be a list of PlanningApplication objects
        self.planning_applications = []


    def addApplication(self, application):
        self.planning_applications.append(application)

    def __repr__(self):
        return self.displayXML()
        
    def displayXML(self):
        """This should display the contents of this object in the planningalerts format.
           i.e. in the same format as this one:
           http://www.planningalerts.com/lambeth.xml
           """
    
        applications_bit = "".join([x.displayXML() for x in self.planning_applications])
    
        return u"""<?xml version="1.0" encoding="UTF-8"?>\n""" + \
                u"<planning>\n" +\
                u"<authority_name>%s</authority_name>\n" %self.authority_name +\
                u"<authority_short_name>%s</authority_short_name>\n" %self.authority_short_name +\
                u"<applications>\n" + applications_bit +\
                u"</applications>\n" +\
                u"</planning>\n"
    
    def save(self): 
        [x.save() for x in self.planning_applications]


class PlanningApplication:
    def __init__(self):
        self.council_reference = None
        self.address = None
        self.postcode = None
        self.description = None
        self.info_url = None
        self.comment_url = None

        # expecting this as a datetime.date object
        self.date_received = None

        # If we can get them, we may as well include OSGB.
        # These will be the entirely numeric version.
        self.osgb_x = None
        self.osgb_y = None

    def __repr__(self):
        return self.displayXML()

    def is_ready(self):
        # This method tells us if the application is complete
        # Because of the postcode default, we can't really
        # check the postcode - make sure it is filled in when
        # you do the address.
        return self.council_reference \
            and self.address \
            and self.description \
            and self.info_url \
            and self.comment_url \
            and self.date_received
    
        
    def displayXML(self):
        #print self.council_reference, self.address, self.postcode, self.description, self.info_url, self.comment_url, self.date_received

        if not self.postcode:
            self.postcode = getPostcodeFromText(self.address)

        contents = [
            u"<council_reference><![CDATA[%s]]></council_reference>" %(self.council_reference),
            u"<address><![CDATA[%s]]></address>" %(self.address),
            u"<postcode><![CDATA[%s]]></postcode>" %self.postcode,
            u"<description><![CDATA[%s]]></description>" %(self.description),
            u"<info_url><![CDATA[%s]]></info_url>" %(self.info_url),
            u"<comment_url><![CDATA[%s]]></comment_url>" %(self.comment_url),
            u"<date_received><![CDATA[%s]]></date_received>" %self.date_received.strftime(date_format),
            ]
        if self.osgb_x:
            contents.append(u"<osgb_x>%s</osgb_x>" %(self.osgb_x))
        if self.osgb_y:
            contents.append(u"<osgb_y>%s</osgb_y>" %(self.osgb_y))

        return u"<application>\n%s\n</application>" %('\n'.join(contents))

    def save(self):
        latlng = None
        if self.postcode != "No Postcode":
            latlng = scraperwiki.geo.gb_postcode_to_latlng(self.postcode)
        scraperwiki.datastore.save(['council_reference'],
          {'council_reference': self.council_reference or '',
           'address': self.address or '',
           'postcode': self.postcode or '',
           'description': self.description or '',
           'info_url': self.info_url or '',
           'comment_url': self.comment_url or '',
           'date_received': self.date_received}, date=self.date_received, latlng=latlng, silent=True)

# Originally made by Duncan Parkes for PlanningAlerts.com

import urllib2
import urllib
import urlparse
import cgi
import re
import datetime

import BeautifulSoup

import scraperwiki.utils

#PlanningUtils = scraperwiki.utils.swimport("planningalertscom-planningutils-library")
#getPostcodeFromText = PlanningUtils.getPostcodeFromText
#PlanningAuthorityResults = PlanningUtils.PlanningAuthorityResults
#PlanningApplication = PlanningUtils.PlanningApplication

# - Browser request: --------------------------
# {POST http://digitalmaidstone.co.uk/swiftlg/apas/run/WPHAPPCRITERIA HTTP/1.0} {Host: digitalmaidstone.co.uk
# Accept: text/html, text/plain, text/css, text/sgml, */*;q=0.01
# Accept-Encoding: gzip
# Accept-Language: en
# Pragma: no-cache
# Cache-Control: no-cache
# User-Agent: Lynx/2.8.6rel.4 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/1.6.3
# Content-type: application/x-www-form-urlencoded
# Content-length: 638
# } %25.MAINBODY.WPACIS.1.=&APNID.MAINBODY.WPACIS.1.=&JUSTLOCATION.MAINBODY.WPACIS.1.=&JUSTDEVDESC.MAINBODY.WPACIS.1.=&DEVDESC.MAINBODY.WPACIS.1.=&SURNAME.MAINBODY.WPACIS.1.=&REGFROMDATE.MAINBODY.WPACIS.1.=01%2F11%2F2007&REGTODATE.MAINBODY.WPACIS.1.=02%2F11%2F2007&DECFROMDATE.MAINBODY.WPACIS.1.=&DECTODATE.MAINBODY.WPACIS.1.=&FINALGRANTFROM.MAINBODY.WPACIS.1.=&FINALGRANTTO.MAINBODY.WPACIS.1.=&APELDGDATFROM.MAINBODY.WPACIS.1.=&APELDGDATTO.MAINBODY.WPACIS.1.=&APEDECDATFROM.MAINBODY.WPACIS.1.=&APEDECDATTO.MAINBODY.WPACIS.1.=&AREA.MAINBODY.WPACIS.1.=&WARD.MAINBODY.WPACIS.1.=&PARISH.MAINBODY.WPACIS.1.=&SEARCHBUTTON.MAINBODY.WPACIS.1.=Search
# server=[digitalmaidstone.co.uk] , port=[80], script=[/swiftlg/apas/run/WPHAPPCRITERIA]
# request_line=[POST /swiftlg/apas/run/WPHAPPCRITERIA HTTP/1.0]

# second page
#http://digitalmaidstone.co.uk/swiftlg/apas/run/WPHAPPSEARCHRES.displayResultsURL?ResultID=243941&
#StartIndex=11&
#SortOrder=APNID:asc&
#DispResultsAs=WPHAPPSEARCHRES&
#BackURL=<a%20href=wphappcriteria.display?paSearchKey=147118>Search%20Criteria

# Date format to enter into search boxes
date_format = "%d/%m/%Y"

class SwiftLGParser:
    search_path = "WPHAPPCRITERIA"
    info_path = "WPHAPPDETAIL.DisplayUrl?theApnID=%s"
    comment_path ="wphmakerep.displayURL?ApnID=%s"

    def _fixHTML(self, html):
        return html

    def _findResultsTable(self, soup):
        """Unless there is just one table in the page, the resuts table,
        override this in a subclass."""
        return soup.table

    def _findTRs(self, results_table):
        """The usual situation is for the results table to contain
        one row of headers, followed by a row per app.
        If this is not the case, override this in a subclass."""
#        import pdb;pdb.set_trace()
        return results_table.findAll("tr")[1:]

    def __init__(self,
                 authority_name,
                 authority_short_name,
                 base_url,
                 debug=False):
        
        self.authority_name = authority_name
        self.authority_short_name = authority_short_name
        self.base_url = base_url

        self.search_url = urlparse.urljoin(base_url, self.search_path)
        self.info_url = urlparse.urljoin(base_url, self.info_path)
        self.comment_url = urlparse.urljoin(base_url, self.comment_path)

        self.debug = debug

        self._results = PlanningAuthorityResults(self.authority_name, self.authority_short_name)


    def getResultsByDayMonthYear(self, day, month, year):
        search_date = datetime.date(year, month, day)
        
        post_data = urllib.urlencode((
                ("REGFROMDATE.MAINBODY.WPACIS.1.", search_date.strftime(date_format)),
                ("REGTODATE.MAINBODY.WPACIS.1.", search_date.strftime(date_format)),
                ("SEARCHBUTTON.MAINBODY.WPACIS.1.", "Search"),
                ))
        
        response = urllib2.urlopen(self.search_url, post_data)
        contents = response.read()

        # Let's give scrapers the change to tidy up any rubbish - I'm looking
        # at you Cannock Chase
        contents = self._fixHTML(contents)

        # Check for the no results warning
        if not contents.count("No Matching Applications Found"):
            soup = BeautifulSoup.BeautifulSoup(contents)

            # Get the links to later pages of results.
            later_pages = soup.findAll("a", {"href": re.compile("WPHAPPSEARCHRES\.displayResultsURL.*StartIndex=\d*.*")})

            for a in ["initial_search"] + later_pages:
                if a != "initial_search":
                    url = a['href']

                    # Example url

                    #http://digitalmaidstone.co.uk/swiftlg/apas/run/WPHAPPSEARCHRES.displayResultsURL?ResultID=244037&StartIndex=11&SortOrder=APNID:asc&DispResultsAs=WPHAPPSEARCHRES&BackURL=<a href=wphappcriteria.display?paSearchKey=147170>Search Criteria</a>

                    # urllib2 doesn't like this url, to make it happy, we'll
                    # get rid of the BackURL parameter, which we don't need.

                    split_url = urlparse.urlsplit(url)
                    qs = split_url[3]

                    # This gets us a dictionary of key to lists of values
                    qsl = cgi.parse_qsl(qs)

                    # Get rid of BackURL
                    qsl.pop(-1)

                    # I think this is safe, as there are no repeats of parameters
                    new_qs = urllib.urlencode(qsl)

                    url = urlparse.urlunsplit(split_url[:3] + (new_qs,) + split_url[4:])

                    this_page_url = urlparse.urljoin(self.base_url, url)
                    response = urllib2.urlopen(this_page_url)
                    contents = response.read()
                    soup = BeautifulSoup.BeautifulSoup(contents)

                results_table = self._findResultsTable(soup)#.body.find("table", {"class": "apas_tbl"})

                trs = self._findTRs(results_table)

                for tr in trs:
                    self._current_application = PlanningApplication()

                    tds = tr.findAll("td")

                    # The first td

                    #<td class="apas_tblContent"><a href="WPHAPPDETAIL.DisplayUrl?theApnID=07/1884&amp;backURL=&lt;a href=wphappcriteria.display?paSearchKey=147125&gt;Search Criteria&lt;/a&gt; &gt; &lt;a href='wphappsearchres.displayResultsURL?ResultID=243950%26StartIndex=1%26SortOrder=APNID:asc%26DispResultsAs=WPHAPPSEARCHRES%26BackURL=&lt;a href=wphappcriteria.display?paSearchKey=147125&gt;Search Criteria&lt;/a&gt;'&gt;Search Results&lt;/a&gt;"></a><a href="wphappcriteria.display?paSearchKey=147125">Search Criteria</a> > <a href="wphappsearchres.displayResultsURL?ResultID=243950%26StartIndex=1%26SortOrder=APNID:asc%26DispResultsAs=WPHAPPSEARCHRES%26BackURL=&lt;a href=wphappcriteria.display?paSearchKey=147125&gt;Search Criteria&lt;/a&gt;"></a><a href="wphappcriteria.display?paSearchKey=147125">Search Criteria</a>'>Search Results">07/1884</td>

                    # The html here is a bit of a mess, and doesn't all get into
                    # the soup.
                    # We can get the reference from the first <a href> in td 0.
                    first_link = tds[0].a['href']

                    app_id = cgi.parse_qs(urlparse.urlsplit(first_link)[3])['theApnID'][0]

                    self._current_application.date_received = search_date
                    self._current_application.council_reference = app_id
                    self._current_application.info_url = self.info_url %(app_id)
                    self._current_application.comment_url = self.comment_url %(app_id)
                    self._current_application.description = tds[1].string.strip()

                    # the second td

                    #<td class="apas_tblContent"><input type="HIDDEN" name="ORDERCOUNTER.PAHEADER.PACIS2.1-1." value="1" class="input-box" size="7" />
                    #LAND ADJ. BRAMBLING, HAWKENBURY ROAD, HAWKENBURY, TN120EA
                    #</td>

                    address = ' '.join([x for x in tds[2].contents if isinstance(x, BeautifulSoup.NavigableString)]).strip()

                    self._current_application.address = address
                    self._current_application.postcode = getPostcodeFromText(address)

                    self._results.addApplication(self._current_application)

        return self._results

    def getResults(self, day, month, year):
        return self.getResultsByDayMonthYear(int(day), int(month), int(year)).displayXML()

    def getResultsRaw(self, day, month, year):
        return self.getResultsByDayMonthYear(int(day), int(month), int(year))

    def saveResults(self, day, month, year):
        return self.getResultsByDayMonthYear(int(day), int(month), int(year)).save()

class EastHertsParser(SwiftLGParser):
    def _findResultsTable(self, soup):
        return soup.findAll("table")[3]

class GwyneddParser(SwiftLGParser):
    def _findResultsTable(self, soup):
        return soup.find("table", {"class": "thinBox"})

class IslingtonParser(SwiftLGParser):
    def _findResultsTable(self, soup):
        return soup.table.table

class MacclesfieldParser(SwiftLGParser):
    def _findResultsTable(self, soup):
        return soup.findAll("table")[6]

class MoleValleyParser(SwiftLGParser):
    def _findResultsTable(self, soup):
#        import pdb;pdb.set_trace()
        return soup.findAll("table")[2]

class SloughParser(SwiftLGParser):
    def _findResultsTable(self, soup):
        return soup.findAll("table")[1]

    def _findTRs(self, results_table):
        return results_table.findAll("tr")[2:]

class CannockChaseParser(SwiftLGParser):
    def _fixHTML(self, html):
        return html.replace('</tr class="tablebody">', '</tr>')

if __name__ == '__main__':
#    parser = SwiftLGParser("Boston Borough Council", "Boston", "http://195.224.121.199/swiftlg/apas/run/")
#    parser = SwiftLGParser("Dudley", "Dudley", "http://www2.dudley.gov.uk/swiftlg/apas/run/")
#    parser = EastHertsParser("East Hertfordshire", "East Herts", "http://e-services.eastherts.gov.uk/swiftlg/apas/run/")
#    parser = GwyneddParser("Gwynedd", "Gwynedd", "http://www.gwynedd.gov.uk/swiftlg/apas/run/")
#    parser = IslingtonParser("Islington", "Islington", "https://www.islington.gov.uk/onlineplanning/apas/run/")
#    parser = SwiftLGParser("Lake District", "Lake District", "http://www.lake-district.gov.uk/swiftlg/apas/run/")
#    parser = SwiftLGParser("Maidstone Borough Council", "Maidstone", "http://digitalmaidstone.co.uk/swiftlg/apas/run/")
#    parser = MoleValleyParser("Mole Valley", "Mole Valley", "http://www.molevalley.gov.uk/swiftlg/apas/run/")
#    parser = SwiftLGParser("Pembrokeshire County Council", "Pembrokeshire", "http://planning.pembrokeshire.gov.uk/swiftlg/apas/run/")
#    parser = SwiftLGParser("Rochdale Metropolitan Borough Council", "Rochdale", "http://www.rochdale.gov.uk/swiftlg/apas/run/")
#    parser = SloughParser("Slough", "Slough", "http://www2.slough.gov.uk/swiftlg/apas/run/")
#    parser = SwiftLGParser("Snowdonia National Park", "Snowdonia", "http://www.snowdonia-npa.gov.uk/swiftlg/apas/run/")
#    parser = SwiftLGParser("St Edmundsbury", "Bury St Edmunds", "http://www.stedmundsbury.gov.uk/swiftlg/apas/run/")
#    parser = MacclesfieldParser("Macclesfield", "Macclesfield", "http://www.planportal.macclesfield.gov.uk/swiftlg/apas/run/")
 parser = SwiftLGParser("Daventry District Council", "Daventry", "http://212.125.73.214/swiftlg/apas/run/wphappcriteria.display")
#    parser = SwiftLGParser("Warrington Borough Council", "Warrington", "http://212.248.237.123:8080/swiftlg/apas/run/wphappcriteria.display")
#    parser = CannockChaseParser("Cannock Chase District Council", "Cannock Chase", "http://planning.cannockchasedc.com/swiftlg/apas/run/wphappcriteria.display")
#    parser = SwiftLGParser("London Borough of Enfield", "Enfield", "http://forms.enfield.gov.uk/swiftlg/apas/run/wphappcriteria.display")
    print parser.getResults(12,6,2009)
#

# To Do:

#1) Check out comment url on Maidstone

#2) Daventry, when it is back up.

#3) Work out what goes wrong with Gwynedd on 06/11/2007

import scraperwiki.utils
import datetime

#swiftlg = scraperwiki.utils.swimport("swift-lg-planning-application-library")

parser = swiftlg.SwiftLGParser("Dun Laoghaire-Rathdown CC", "DLR", "http://planning.dlrcoco.ie/swiftlg/apas/run/wphappcriteria.display")

# results = parser.getResultsRaw(11,10,2010)
# results.save()

today = datetime.date.today()
for i in range(365):
   day = today - datetime.timedelta(days=i)
   parser.saveResults(day.day, day.month, day.year)

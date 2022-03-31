# AdultDVDMarketplace
# Update: 30 March 2022
# Description: AdultDVDMarketplace agent for Plex.  Any problems, hit up Darklyter
import re
import datetime
import random
import urllib2

# preferences
preference = Prefs
DEBUG = preference['debug']
if DEBUG:
  Log('Agent debug logging is enabled!')
else:
  Log('Agent debug logging is disabled!')

# URLS
ADM_BASEURL = 'https://www.adultdvdmarketplace.com'
ADM_SEARCH_MOVIES = ADM_BASEURL + '/xcart/adult_dvd/dvd_search.php?type=title&search=%s'
ADM_MOVIE_INFO = ADM_BASEURL + '/dvd_view_%s.html'

scoreprefs = int(preference['goodscore'].strip())
if scoreprefs > 1:
    GOOD_SCORE = scoreprefs
else:
    GOOD_SCORE = 98
if DEBUG:Log('Result Score: %i' % GOOD_SCORE)

INITIAL_SCORE = 100


def Start():
  HTTP.CacheTime = CACHE_1MINUTE
  HTTP.SetHeader('User-agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)')

def ValidatePrefs():
  pass

class ADMAgent(Agent.Movies):
  name = 'Adult DVD Marketplace'
  languages = [Locale.Language.English]
  primary_provider = True
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang):
    title = media.name
    if media.primary_metadata is not None:
      title = media.primary_metadata.title

    query = String.URLEncode(String.StripDiacritics(title.replace('-','')))

    # resultarray[] is used to filter out duplicate search results
    resultarray=[]
    if DEBUG: Log('Search Query: %s' % str(ADM_SEARCH_MOVIES % query))
    # Finds the entire media enclosure <DIV> elements then steps through them
    for movie in HTML.ElementFromURL(ADM_SEARCH_MOVIES % query).xpath('//div[@class="row"]/div/div[contains(@class, "product-col")]/div[@class="caption"]/h4/a'):
      # curName = The text in the 'title' p
      # ~ try:
        moviehref = movie.xpath('./@href')[0].strip()
        curName = movie.xpath('./text()')[0].strip()
        if DEBUG: Log('Initial Result Name found: %s' % str(curName))
        if curName.count(', The'):
          curName = 'The ' + curName.replace(', The','',1)
        yearName = curName
        relName = curName

        # curID = the ID portion of the href in 'movie'
        curID = re.search(r'_(\d+).html', moviehref).group(1)
        score = INITIAL_SCORE - Util.LevenshteinDistance(title.lower(), curName.lower())

        if curName.lower().count(title.lower()):
            results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))
        elif (score >= GOOD_SCORE):
            results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))

      # ~ except: pass

    results.Sort('score', descending=True)

  def update(self, metadata, media, lang):
    if DEBUG: Log('Beginning Update...')
    html = HTML.ElementFromURL(ADM_MOVIE_INFO % metadata.id)
    metadata.title = media.title
    if DEBUG: Log('Title Metadata Key: [Movie Title]   Value: [%s]', metadata.title)

    # Thumb and Poster
    try:
      if DEBUG: Log('Looking for thumb and poster')
      img = html.xpath('//a[./strong[contains(text(), "Front Cover")]]/../preceding-sibling::a/img')[0]
      thumbUrl = img.get('src')
      thumb = HTTP.Request(thumbUrl)

      img = html.xpath('//a[./strong[contains(text(), "Front Cover")]]')[0]
      posterUrl = img.get('href')
      metadata.posters[posterUrl] = Proxy.Preview(thumb)
    except: pass

    # Summary.
    try:
        summary = html.xpath('//div[contains(@class, "product-details")]/h3[contains(text(), "Description")]/following-sibling::p')[0].text_content().strip()
        Log('Summary Found: %s' %str(summary))
        metadata.summary = summary
    except Exception, e:
      Log('Got an exception while parsing summary %s' %str(e))

    # Studio.
    try:
        studio = html.xpath('//h3[contains(text(), "Details")]/following-sibling::ul/li/span[contains(text(), "Studio")]/following-sibling::a/span/text()')[0].strip()
        Log('Studio Found: %s' %str(studio))
        metadata.studio = studio
    except Exception, e:
      Log('Got an exception while parsing studio %s' %str(e))

    # Release Date.
    try:
        releasedate = html.xpath('//h3[contains(text(), "Details")]/following-sibling::ul/li/span[contains(text(), "Released")]/following-sibling::text()')[0].strip()
        if releasedate:
            if re.search(r'(\d{,2})/(\d{4})', releasedate):
                releasedate = re.search(r'(\d{,2})/(\d{4})', releasedate)
                parseddate = releasedate.group(2) + "-" + releasedate.group(1) + "-01"
                Log('releasedate Found: %s' %str(parseddate))
                metadata.originally_available_at = Datetime.ParseDate(parseddate).date()
                metadata.year = int(releasedate.group(2))
    except Exception, e:
      Log('Got an exception while parsing releasedate %s' %str(e))


    # Cast
    try:
      metadata.roles.clear()
      actors = html.xpath('//h3[contains(text(), "Cast")]/following-sibling::a/text()')
      for actor in actors:
        actor = actor.strip()
        if DEBUG: Log('Adding Star: %s' % actor)
        role = metadata.roles.new()
        role.name = actor

    except Exception, e:
      Log('Got an exception while parsing cast %s' %str(e))

    # Genres
    try:
      genrelist = []
      metadata.genres.clear()
      ignoregenres = [x.lower().strip() for x in preference['ignoregenres'].split('|')]
      genres = html.xpath('//h3[contains(text(), "Details")]/following-sibling::ul/li/span[contains(text(), "Category")]/following-sibling::a/text()')
      for genre in genres:
          genre = genre.strip()
          genrelist.append(genre)
          if not genre.lower().strip() in ignoregenres: metadata.genres.add(genre)
      if DEBUG: Log('Found Genres: %s' % (' | '.join(genrelist)))

    except Exception, e:
      Log('Got an exception while parsing genres %s' %str(e))

  #Just a function to check to see if a url (image here) exists
  def file_exists(self, url):
    request = urllib2.Request(url)
    request.get_method = lambda : 'HEAD'
    try:
        response = urllib2.urlopen(request)
        #Log('Response for File Exist check: %s' % str(response.getcode()))
        #Log('URL Actually retrieved: %s' % str(response.geturl()))
        #Log('Headers retrieved from pull: %s' % str(response.info()))
        return True
    except:
        return False

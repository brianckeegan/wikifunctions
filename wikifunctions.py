import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import unquote, quote
from copy import deepcopy
import requests, re

def response_to_revisions(json_response):
    if type(json_response['query']['pages']) == dict:
        page_id = list(json_response['query']['pages'].keys())[0]
        return json_response['query']['pages'][page_id]['revisions']
    elif type(json_response['query']['pages']) == list:
        if 'revisions' in json_response['query']['pages'][0]:
            return json_response['query']['pages'][0]['revisions']
        else:
            return list()
    else:
        raise ValueError("There are no revisions in the JSON")
        
def get_all_page_revisions(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Takes Wikipedia page title and returns a DataFrame of revisions
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - a Boolean value for whether to follow redirects to another page
        
    Returns:
    df - a pandas DataFrame where each row is a revision and columns correspond
         to meta-data such as parentid, revid, sha1, size, timestamp, and user name
    """
    
    # A container to store all the revisions
    revision_list = list()
    
    # Set up the query
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['titles'] = page_title
    query_params['prop'] = 'revisions'
    query_params['rvprop'] = 'ids|userid|comment|timestamp|user|size|sha1'
    query_params['rvlimit'] = 500
    query_params['rvdir'] = 'newer'
    query_params['format'] = 'json'
    query_params['redirects'] = redirects
    query_params['formatversion'] = 2
    
    # Make the query
    json_response = requests.get(url = query_url, params = query_params).json()

    # Add the temporary list to the parent list
    revision_list += response_to_revisions(json_response)

    # Loop for the rest of the revisions
    while True:

        # Newer versions of the API return paginated results this way
        if 'continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvcontinue'] = json_response['continue']['rvcontinue']
            json_response = requests.get(url = query_url, params = query_continue_params).json()
            revision_list += response_to_revisions(json_response)
        
        # Older versions of the API return paginated results this way
        elif 'query-continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvstartid'] = json_response['query-continue']['revisions']['rvstartid']
            json_response = requests.get(url = query_url, params = query_continue_params).json()
            revision_list += response_to_revisions(json_response)
        
        # If there are no more revisions, stop
        else:
            break

    # Convert to a DataFrame
    df = pd.DataFrame(revision_list)

    # Add in some helpful fields to the DataFrame
    final_title = json_response['query']['pages'][0]['title']
    df['page'] = final_title
    df['userid'] = df['userid'].fillna(0).apply(lambda x:str(int(x)))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].apply(lambda x:x.date())
    df['diff'] = df['size'].diff()
    df['lag'] = df['timestamp'].diff()/pd.Timedelta(1,'s')
    df['age'] = (df['timestamp'] - df['timestamp'].min())/pd.Timedelta(1,'d')
    
    return df
    
def get_page_revisions_from_date(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1, start='2001-01-01',stop='today'):
    """Takes Wikipedia page title and returns a DataFrame of revisions
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - a Boolean value for whether to follow redirects to another page
    start - a string, datetime, or Timestamp object when revisions should start
    stop - a string, datetime, or Timestamp object when revisions should stop
        
    Returns:
    df - a pandas DataFrame where each row is a revision and columns correspond
         to meta-data such as parentid, revid, sha1, size, timestamp, and user name
    """
    
    # A container to store all the revisions
    revision_list = list()
    
    # Fix dates
    start = datetime.strftime(pd.to_datetime(start), '%Y-%m-%dT%H:%M:%SZ')
    stop = datetime.strftime(pd.to_datetime(stop), '%Y-%m-%dT%H:%M:%SZ')
    
    # Set up the query
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['titles'] = page_title
    query_params['prop'] = 'revisions'
    query_params['rvprop'] = 'ids|userid|comment|timestamp|user|size|sha1'
    query_params['rvlimit'] = 500
    query_params['rvdir'] = 'newer'
    query_params['format'] = 'json'
    query_params['redirects'] = redirects
    query_params['rvstart'] = start
    query_params['rvend'] = stop
    query_params['formatversion'] = 2
    
    # Make the query
    json_response = requests.get(url = query_url, params = query_params).json()

    # Add the temporary list to the parent list
    revision_list += response_to_revisions(json_response)

    # Loop for the rest of the revisions
    while True:

        # Newer versions of the API return paginated results this way
        if 'continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvcontinue'] = json_response['continue']['rvcontinue']
            json_response = requests.get(url = query_url, params = query_continue_params).json()
            revision_list += response_to_revisions(json_response)
        
        # Older versions of the API return paginated results this way
        elif 'query-continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvstartid'] = json_response['query-continue']['revisions']['rvstartid']
            json_response = requests.get(url = query_url, params = query_continue_params).json()
            revision_list += response_to_revisions(json_response)
        
        # If there are no more revisions, stop
        else:
            break

    # Convert to a DataFrame
    df = pd.DataFrame(revision_list)

    # Add in some helpful fields to the DataFrame
    final_title = json_response['query']['pages'][0]['title']
    df['page'] = final_title
    df['userid'] = df['userid'].fillna(0).apply(lambda x:str(int(x)))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].apply(lambda x:x.date())
    df['diff'] = df['size'].diff()
    df['lag'] = df['timestamp'].diff()/pd.Timedelta(1,'s')
    df['age'] = (df['timestamp'] - df['timestamp'].min())/pd.Timedelta(1,'d')

    return df
    
def chunks(l, n=50):
    """
    Yield successive n-sized chunks from l.
    Adapted from: https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks    
    """
    for i in range(0, len(l), n):
        yield l[i:i + n]

def get_redirects_linking_here(page_title, endpoint="en.wikipedia.org/w/api.php", namespace=0):
    """Takes a page title and returns a list of redirects linking to the page
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    namespace - limit to pages from a specific namespace, defaults to 0
    
    Returns:
    linkshere - a list of strings with the redirect titles
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    
    lh_list = list()
    
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['titles'] = page_title
    query_params['prop'] = 'linkshere'
    query_params['lhprop'] = 'title|redirect'
    query_params['lhnamespace'] = namespace
    query_params['lhshow'] = 'redirect'
    query_params['lhlimit'] = 500
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    # Make the query
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'linkshere' in json_response['query']['pages'][0]:
        subquery_lh_list = json_response['query']['pages'][0]['linkshere']
        lh_list += subquery_lh_list
    
        while True:

            if 'continue' not in json_response:
                break

            else:
                query_continue_params = deepcopy(query_params)
                query_continue_params['lhcontinue'] = json_response['continue']['lhcontinue']
                json_response = requests.get(url = query_url, params = query_continue_params).json()
                subquery_lh_list = json_response['query']['pages'][0]['linkshere']
                lh_list += subquery_lh_list
    
    return [i['title'] for i in lh_list]

def get_redirects_map(page_list, endpoint="en.wikipedia.org/w/api.php"):
    redirects_d = {}
    
    chunked = list(chunks(page_list,50))
    
    for chunk in chunked:
        query_url = "https://{0}".format(endpoint)
        query_params = {}
        query_params['action'] = 'query'
        query_params['prop'] = 'info'
        query_params['titles'] = '|'.join(chunk)
        query_params['redirects'] = 1
        query_params['format'] = 'json'
        query_params['formatversion'] = 2
        json_response = requests.get(url=query_url,params=query_params).json()
        
        if 'redirects' in json_response['query']:
            mapping = {redir['from']:redir['to'] for redir in json_response['query']['redirects']}
            redirects_d.update(mapping)
            
    return redirects_d
        

def resolve_redirects(page_list,endpoint="en.wikipedia.org/w/api.php"):
    resolved_page_list = []
    
    chunked = list(chunks(page_list,50))
    
    for chunk in chunked:
        query_url = "https://{0}".format(endpoint)
        query_params = {}
        query_params['action'] = 'query'
        query_params['prop'] = 'info'
        query_params['titles'] = '|'.join(chunk)
        query_params['redirects'] = 1
        query_params['format'] = 'json'
        query_params['formatversion'] = 2
        json_response = requests.get(url=query_url,params=query_params).json()
        
        if 'pages' in json_response['query']:
            pages = [page['title'] for page in json_response['query']['pages']]
            resolved_page_list += pages
            
    return resolved_page_list

def get_page_raw_content(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Takes a page title and returns the raw HTML.
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    
    Returns:
    outlinks_per_lang - a dictionary keyed by language returning a dictionary 
        keyed by page title returning a list of outlinks
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    #req = requests.get('https://{2}.wikipedia.org/w/api.php?action=parse&format=json&page={0}&redirects={1}&prop=text&disableeditsection=1&disabletoc=1'.format(page_title,redirects,lang))
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['page'] = page_title
    query_params['redirects'] = redirects
    query_params['prop'] = 'text'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        markup = json_response['parse']['text']
        final_title = json_response['parse']['title']
    else:
        markup = str()
        final_title = page_title
    
    return markup

def parse_to_links(input,is_json=True):
    # Initialize an empty list to store the links
    outlinks_list = []
    
    if is_json:
        page_html = input['parse']['text']#['*']
    else:
        page_html = input

    # Parse the HTML into Beautiful Soup
    soup = BeautifulSoup(page_html,'lxml')

    # Remove sections at end
    bad_sections = ['See_also','Notes','References','Bibliography','External_links']
    bad_titles = ['Special:','Wikipedia:','Help:','Template:','Category:','International Standard','Portal:','s:','File:','Digital object identifier','(page does not exist)']
    
    sections = soup.find_all('h2')
    for section in sections:
        if section.span['id'] in bad_sections:

            # Clean out the divs
            div_siblings = section.find_next_siblings('div')
            for sibling in div_siblings:
                sibling.clear()

            # Clean out the ULs
            ul_siblings = section.find_next_siblings('ul')
            for sibling in ul_siblings:
                sibling.clear()

    # Delete tags associated with templates
    for tag in soup.find_all('tr'):
        tag.replace_with('')

    # For each paragraph tag, extract the titles within the links
    for para in soup.find_all('p'):
        for link in para.find_all('a'):
            if link.has_attr('title'):
                title = link['title']
                # Ignore links that aren't interesting or are redlinks
                if all(bad not in title for bad in bad_titles) and 'redlink' not in link['href']:
                    outlinks_list.append(title)

    # For each unordered list, extract the titles within the child links
    for unordered_list in soup.find_all('ul'):
        for item in unordered_list.find_all('li'):
            for link in item.find_all('a'):
                if link.has_attr('title'):
                    title = link['title']
                    # Ignore links that aren't interesting or are redlinks
                    if all(bad not in title for bad in bad_titles) and 'redlink' not in link['href']:
                        outlinks_list.append(title)
    
    return outlinks_list
        
def get_revision_raw_content(revid, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Takes a revision ID and returns the raw HTML.
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    
    Returns:
    outlinks_per_lang - a dictionary keyed by language returning a dictionary 
        keyed by page title returning a list of outlinks
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    #req = requests.get('https://{2}.wikipedia.org/w/api.php?action=parse&format=json&page={0}&redirects={1}&prop=text&disableeditsection=1&disabletoc=1'.format(page_title,redirects,lang))
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['oldid'] = revid
    query_params['prop'] = 'text'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        markup = json_response['parse']['text']
        final_title = json_response['parse']['title']
    else:
        markup = str()
        final_title = page_title
        
    return markup
    
def get_page_outlinks(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Takes a page title and returns a list of wiki-links on the page. The 
    list may contain duplicates and the position in the list is approximately 
    where the links occurred.
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    
    Returns:
    outlinks_per_lang - a dictionary keyed by language returning a dictionary 
        keyed by page title returning a list of outlinks
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    #req = requests.get('https://{2}.wikipedia.org/w/api.php?action=parse&format=json&page={0}&redirects={1}&prop=text&disableeditsection=1&disabletoc=1'.format(page_title,redirects,lang))
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['page'] = page_title
    query_params['redirects'] = redirects
    query_params['prop'] = 'text'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        links = parse_to_links(json_response)
        final_title = json_response['parse']['title']
    else:
        links = list()
        final_title = page_title
        
    return links    
    
def get_revision_outlinks(revid, endpoint='en.wikipedia.org/w/api.php'):
    """Takes a page title and returns a list of wiki-links on the page. The 
    list may contain duplicates and the position in the list is approximately 
    where the links occurred.
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    
    Returns:
    outlinks_per_lang - a dictionary keyed by language returning a dictionary 
        keyed by page title returning a list of outlinks
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    #req = requests.get('https://{2}.wikipedia.org/w/api.php?action=parse&format=json&page={0}&redirects={1}&prop=text&disableeditsection=1&disabletoc=1'.format(page_title,redirects,lang))
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['oldid'] = revid
    query_params['prop'] = 'text'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        return parse_to_links(json_response)
    else:
        return list()

    return links
    
def get_page_externallinks(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Takes a revision id and returns a list of external links on the revision
    
    revid - a numeric revision id as a string
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    parse - 1 or 0 for whether to return the raw HTML or paragraph text
    
    Returns:
    str - a list of strings with the URLs
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    # req = requests.get('https://{2}.wikipedia.org/w/api.php?action=parse&format=json&oldid={0}&redirects={1}&prop=externallinks&disableeditsection=1&disabletoc=1'.format(revid,redirects,lang))
    
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['page'] = page_title
    query_params['redirects'] = redirects
    query_params['prop'] = 'externallinks'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        if 'externallinks' in json_response['parse']:
            links = json_response['parse']['externallinks']
            final_title = json_response['parse']['title']
    else:
        links = list()
        final_title = page_title
        
    return links
            
def get_revision_externallinks(revid, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Takes a revision id and returns a list of external links on the revision
    
    revid - a numeric revision id as a string
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    parse - 1 or 0 for whether to return the raw HTML or paragraph text
    
    Returns:
    str - a list of strings with the URLs
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    # req = requests.get('https://{2}.wikipedia.org/w/api.php?action=parse&format=json&oldid={0}&redirects={1}&prop=externallinks&disableeditsection=1&disabletoc=1'.format(revid,redirects,lang))
    
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['oldid'] = revid
    query_params['prop'] = 'externallinks'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        if 'externallinks' in json_response['parse']:
            links = json_response['parse']['externallinks']
            final_title = json_response['parse']['title']
    else:
        links = list()
        final_title = page_title
        
    return links
        
def parse_to_text(input,is_json=True,parse_text=True):
    if is_json:
        page_html = input['parse']['text']#['*']
    else:
        page_html = input
    
    # Parse the HTML into Beautiful Soup
    soup = BeautifulSoup(page_html,'lxml')

    # Remove sections at end
    bad_sections = ['See_also','Notes','References','Bibliography','External_links']
    sections = soup.find_all('h2')
    for section in sections:
        if section.span['id'] in bad_sections:

            # Clean out the divs
            div_siblings = section.find_next_siblings('div')
            for sibling in div_siblings:
                sibling.clear()

            # Clean out the ULs
            ul_siblings = section.find_next_siblings('ul')
            for sibling in ul_siblings:
                sibling.clear()

    # Get all the paragraphs
    paras = soup.find_all('p')

    text_list = []

    for para in paras:
        if parse_text:
            _s = para.text
            # Remove the citations
            _s = re.sub(r'\[[0-9]+\]','',_s)
            text_list.append(_s)
        else:
            text_list.append(str(para))

    return '\n'.join(text_list)
    
def get_page_content(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1, parsed_text=1):
    """Takes a page_title and returns a (large) plaintext string of the content 
    of the revision.
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    parse - 1 to return plain text or 0 to return raw HTML
    
    Returns:
    str - a (large) plaintext string of the content of the revision
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['page'] = page_title
    query_params['redirects'] = redirects
    query_params['prop'] = 'text'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        return parse_to_text(json_response,parsed_text)
    
    
def get_revision_content(revid,endpoint='en.wikipedia.org/w/api.php',parsed_text=1):
    """Takes a page_title and returns a (large) plaintext string of the content 
    of the revision.
    
    revid - the revision ID of a revision on a wiki project
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
    parse - 1 to return plain text or 0 to return raw HTML
    
    Returns:
    str - a (large) plaintext string of the content of the revision
    """
    
    # Get the response from the API for a query
    # After passing a page title, the API returns the HTML markup of the current article version within a JSON payload
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'parse'
    query_params['oldid'] = revid
    query_params['prop'] = 'text'
    query_params['disableeditsection'] = 1
    query_params['disabletoc'] = 1
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'parse' in json_response.keys():
        return parse_to_text(json_response,parsed_text)
    
def get_page_redirects(page_list,endpoint='en.wikipedia.org/w/api.php'):

    chunked_page_list = list(chunks(page_list))
    
    page_redirects = {}
    
    for chunk in chunked_page_list:
        page_titles = '|'.join(chunk)
        
        # Set up the query
        query_url = "https://{0}".format(endpoint)
        query_params = {}
        query_params['action'] = 'query'
        query_params['titles'] = page_titles
        query_params['prop'] = 'info'
        query_params['format'] = 'json'
        query_params['redirects'] = 1
        query_params['formatversion'] = 2
        
        # Make the query
        json_response = requests.get(url = query_url, params = query_params).json()

        # Add the redirects to the dictionary
        if 'redirects' in json_response['query']:

            for _rd in json_response['query']['redirects']:
                page_redirects[_rd['from']] = _rd['to']
            
    # Include the non-redirects for the sake of completeness
    for page in page_list:
        if page not in page_redirects:
            page_redirects[page] = page
            
    return page_redirects

def get_interlanguage_links(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """The function accepts a page_title and returns a dictionary containing 
    the title of the page in its other languages
       
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    redirects - 1 or 0 for whether to follow page redirects, defaults to 1
       
    Returns:
    langlink_dict - a dictionary keyed by lang codes and page title as values
    """
    
    #query_string = "https://{1}.wikipedia.org/w/api.php?action=query&format=json&prop=langlinks&formatversion=2&titles={0}&llprop=autonym|langname&lllimit=500".format(page_title,lang)
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['prop'] = 'langlinks'
    query_params['titles'] = page_title
    query_params['redirects'] = redirects
    query_params['llprop'] = 'autonym|langname'
    query_params['lllimit'] = 500
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    json_response = requests.get(url=query_url,params=query_params).json()
    
    interlanguage_link_dict = dict()
    start_lang = endpoint.split('.')[0]
    if 'title' in json_response['query']['pages'][0]:
        final_title = json_response['query']['pages'][0]['title']
        interlanguage_link_dict[start_lang] = final_title
    else:
        final_title = page_title
        interlanguage_link_dict[start_lang] = final_title

    if 'langlinks' in json_response['query']['pages'][0]:
        langlink_dict = json_response['query']['pages'][0]['langlinks']

        for d in langlink_dict:
            lang = d['lang']
            title = d['title']
            interlanguage_link_dict[lang] = title
            
    return interlanguage_link_dict
    
def get_pageviews(page_title,endpoint='en.wikipedia.org',start='20150701',stop='today',useragent='brian.keegan@colorado.edu'):
    """Takes Wikipedia page title and returns a all the various pageview records
    
    page_title - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    start - a date string in a YYYYMMDD format, defaults to 20150701 (earliest date)
    stop - a date string in a YYYYMMDD format, defaults to today
        
    Returns:
    df - a DataFrame indexed by date and multi-columned by agent and access type
    """
            
    quoted_page_title = quote(page_title, safe='')
    date_from = datetime.strftime(pd.to_datetime(start),'%Y%m%d')
    date_to = datetime.strftime(pd.to_datetime(stop),'%Y%m%d')
    
    #for access in ['all-access','desktop','mobile-app','mobile-web']:
    #for agent in ['all-agents','user','spider','bot']:
    s = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{1}/{2}/{3}/{0}/daily/{4}/{5}".format(quoted_page_title,endpoint,'all-access','user',date_from,date_to)
    headers = {'User-Agent':useragent}
    json_response = requests.get(s,headers=headers).json()
    
    if 'items' in json_response:
        df = pd.DataFrame(json_response['items'])
    else:
        raise KeyError('There is no "items" key in the JSON response.')
        
    df = df[['timestamp','views']]
    df['timestamp'] = pd.to_datetime(df['timestamp'],format='%Y%m%d%H')
    s = df.set_index('timestamp')['views']
        
    return s
    
def get_category_memberships(page_title,endpoint='en.wikipedia.org/w/api.php'):
    """The function accepts a page_title and returns a list of categories
    the page is a member of
    
    category_title - a string of the page name
    
    Returns:
    members - a list containing strings of the categories of which the page is a mamber
    
    """
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['prop'] = 'categories'
    query_params['titles'] = page_title
    query_params['clprop'] = 'timestamp'
    query_params['clshow'] = '!hidden'
    query_params['cllimit'] = 500
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
    
    json_response = requests.get(url=query_url,params=query_params).json()

    categories = list()

    if 'pages' in json_response['query']:
        if 'categories' in json_response['query']['pages'][0]:
            for category in json_response['query']['pages'][0]['categories']:
                title = category['title']#.split(':')[1]
                categories.append(title)
                #timestamp = category['timestamp']
                #categories.append({title:timestamp})
            
    return categories

def get_category_subcategories(category_title,endpoint='en.wikipedia.org/w/api.php'):
    """The function accepts a category_title and returns a list of the category's sub-categories
    
    category_title - a string (including "Category:" prefix) of the category name
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    
    Returns:
    members - a list containing strings of the sub-categories in the category
    
    """
    # Replace spaces with underscores
    category_title = category_title.replace(' ','_')
    
    # Make sure "Category:" appears in the title
    if 'Category:' not in category_title:
        category_title = 'Category:' + category_title
    
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['list'] = 'categorymembers'
    query_params['cmtitle'] = category_title
    query_params['cmtype'] = 'subcat'
    query_params['cmprop'] = 'title'
    query_params['cmlimit'] = 500
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
        
    json_response = requests.get(url = query_url, params = query_params).json()
    
    members = list()
    
    if 'categorymembers' in json_response['query']:
        for member in json_response['query']['categorymembers']:
            members.append(member['title'])
            
    return members

def get_category_members(category_title,depth=1,endpoint='en.wikipedia.org/w/api.php',namespace=0,prepend=True):
    """The function accepts a category_title and returns a list of category members
    
    category_title - a string (including "Category:" prefix) of the category named
    depth - the depth of sub-categories to crawl
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    namespace - namespaces to include (multiple namespaces separated by pipes, e.g. "0|1|2")
    
    Returns:
    members - a list containing strings of the page titles in the category
    
    """
    # Replace spaces with underscores
    category_title = category_title.replace(' ','_')
    
    # Make sure "Category:" appears in the title
    if prepend and 'Category:' not in category_title:
        category_title = 'Category:' + category_title
    
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['list'] = 'categorymembers'
    query_params['cmtitle'] = category_title
    query_params['cmprop'] = 'title'
    query_params['cmnamespace'] = namespace
    query_params['cmlimit'] = 500
    query_params['format'] = 'json'
    query_params['formatversion'] = 2
        
    json_response = requests.get(url = query_url, params = query_params).json()

    members = list()
    
    if depth < 0:
        return members
    
    if 'categorymembers' in json_response['query']:
        for member in json_response['query']['categorymembers']:
            members.append(member['title'])
            
    while True:
        if 'continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['cmcontinue'] = json_response['continue']['cmcontinue']
            json_response = requests.get(url = query_url, params = query_continue_params).json()
            if 'categorymembers' in json_response['query']:
                for member in json_response['query']['categorymembers']:
                    members.append(member['title'])
        else:
            break
            
    subcats = get_category_subcategories(category_title,endpoint=endpoint)
    
    for subcat in subcats:
        members += get_category_members(subcat,depth=depth-1,endpoint=endpoint,namespace=namespace)
            
    return members

def get_user_info(username_list,endpoint='en.wikipedia.org/w/api.php'):
    """Takes a list of Wikipedia usernames and returns a JSON of their information
    
    username_list - a list of strings for all the usernames
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
        
    Returns:
    users_info - a list of information about users
    
    API endpoint docs: https://www.mediawiki.org/wiki/API:Users
    """
    users_info = []
    
    chunked_username_list = list(chunks(username_list,50))
    
    for chunk in chunked_username_list:
        usernames = '|'.join(chunk)
        
        query_url = "https://{0}".format(endpoint)
        query_params = {}
        query_params['action'] = 'query'
        query_params['list'] = 'users'
        query_params['ususers'] = usernames
        query_params['usprop'] = 'blockinfo|groups|editcount|registration|gender'
        query_params['format'] = 'json'
        query_params['formatversion'] = 2
        
        json_response = requests.get(url = query_url, params = query_params).json()
        if 'query' in json_response:
            users_info += json_response['query']['users']
    
    return users_info

def get_user_contributions(username,endpoint='en.wikipedia.org/w/api.php', redirects=1,start='2001-01-01',stop='today'):
    """Takes Wikipedia username and returns a DataFrame of user contributions
    
    username - a string with the title of the page on Wikipedia
    endpoint - a string that points to the web address of the API.
        This defaults to the English Wikipedia endpoint: 'en.wikipedia.org/w/api.php'
        Changing the two letter language code will return a different language edition
        The Wikia endpoints are slightly different, e.g. 'starwars.wikia.com/api.php'
    start - a string, datetime, or Timestamp for the earliest user contributions to retrieve
    stop - a string, datetime, or Timestamp for the latest user contributions to retrieve
        
    Returns:
    usercontribs_df - a DataFrame containing the revision meta-data such as 
        parentid, revid,sha1, size, timestamp, and user name
        
    API endpoint docs: https://www.mediawiki.org/wiki/API:Usercontribs
    """
    start = datetime.strftime(pd.to_datetime(start), '%Y-%m-%dT%H:%M:%SZ')
    stop = datetime.strftime(pd.to_datetime(stop), '%Y-%m-%dT%H:%M:%SZ')
    
    revision_list = list()
    
    # Set up the query
    query_url = "https://{0}".format(endpoint)
    query_params = {}
    query_params['action'] = 'query'
    query_params['list'] = 'usercontribs'
    query_params['ucuser'] = username
    query_params['ucprop'] = 'ids|title|comment|timestamp|flags|size|sizediff'
    query_params['ucstart'] = start
    query_params['ucend'] = stop
    query_params['uclimit'] = 500
    query_params['ucdir'] = 'newer'
    query_params['format'] = 'json'
    query_params['redirects'] = 1
    query_params['formatversion'] = 2
    
    # Make the query
    json_response = requests.get(url = query_url, params = query_params).json()
    
    if 'query' in json_response:
        
        subquery_revision_list = json_response['query']['usercontribs']

        revision_list += subquery_revision_list

        while True:

            if 'continue' not in json_response:
                break

            else:
                query_continue_params = deepcopy(query_params)
                query_continue_params['uccontinue'] = json_response['continue']['uccontinue']
                json_response = requests.get(url = query_url, params = query_continue_params).json()
                subquery_revision_list = json_response['query']['usercontribs']
                revision_list += subquery_revision_list
                #time.sleep(1)
       
    df = pd.DataFrame(revision_list)
    
    if len(df.columns) > 0:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].apply(lambda x:x.date())
        df['userid'] = df['userid'].fillna(0).apply(lambda x:str(int(x)))

    return df
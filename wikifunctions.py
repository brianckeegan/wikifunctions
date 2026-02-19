import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import unquote, quote
from copy import deepcopy
import os
import requests, re

DEFAULT_USER_AGENT = os.environ.get(
    "WIKIFUNCTIONS_USER_AGENT",
    "wikifunctions/0.1 (https://github.com/briankeegan/wikifunctions)",
)
DEFAULT_REQUEST_TIMEOUT = float(os.environ.get("WIKIFUNCTIONS_TIMEOUT_SECONDS", "30"))


def _get_json(*args, **kwargs):
    """Execute an HTTP GET request and return parsed JSON.

    Adds a default `User-Agent` and timeout, preserves any caller-provided
    headers, and raises a descriptive error when the MediaWiki API returns an
    explicit `"error"` payload.

    Args:
        *args: Positional arguments forwarded to `requests.get`.
        **kwargs: Keyword arguments forwarded to `requests.get`.

    Returns:
        object: Parsed JSON response body.

    Raises:
        requests.HTTPError: If the HTTP response has a non-2xx status.
        RuntimeError: If the JSON response contains a MediaWiki `"error"` key.
    """
    headers = kwargs.pop("headers", None)
    request_headers = dict(headers) if headers else {}
    request_headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
    kwargs["headers"] = request_headers
    kwargs.setdefault("timeout", DEFAULT_REQUEST_TIMEOUT)
    response = requests.get(*args, **kwargs)
    response.raise_for_status()
    json_response = response.json()
    if isinstance(json_response, dict) and "error" in json_response:
        api_error = json_response["error"]
        raise RuntimeError(
            "MediaWiki API error ({0}): {1}".format(
                api_error.get("code", "unknown"),
                api_error.get("info", "No error detail was provided."),
            )
        )
    return json_response


def _extract_section_id(section):
    """Return the section id from an `h2` tag, if present.

    Args:
        section (bs4.element.Tag): Heading tag to inspect.

    Returns:
        str | None: Heading id from the tag itself or a nested `<span id=...>`.
    """
    if section.has_attr("id"):
        return section.get("id")
    span = section.find("span", id=True)
    if span is not None:
        return span.get("id")
    return None


def response_to_revisions(json_response):
    """Extract a revisions list from a MediaWiki `query` response.

    Args:
        json_response (dict): MediaWiki API response containing `query.pages`.

    Returns:
        list: Revision dictionaries, or an empty list when no revisions exist.

    Raises:
        ValueError: If `query.pages` is not a supported shape.
    """
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
    """Return the full revision history for a page.

    Args:
        page_title (str): Page title on the target wiki.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects.

    Returns:
        pandas.DataFrame: Revision metadata in chronological order, with
        computed helper fields where source columns are available.
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
    json_response = _get_json(url = query_url, params = query_params)

    # Add the temporary list to the parent list
    revision_list += response_to_revisions(json_response)

    # Loop for the rest of the revisions
    while True:

        # Newer versions of the API return paginated results this way
        if 'continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvcontinue'] = json_response['continue']['rvcontinue']
            json_response = _get_json(url = query_url, params = query_continue_params)
            revision_list += response_to_revisions(json_response)
        
        # Older versions of the API return paginated results this way
        elif 'query-continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvstartid'] = json_response['query-continue']['revisions']['rvstartid']
            json_response = _get_json(url = query_url, params = query_continue_params)
            revision_list += response_to_revisions(json_response)
        
        # If there are no more revisions, stop
        else:
            break

    # Convert to a DataFrame
    df = pd.DataFrame(revision_list)

    # Add in some helpful fields to the DataFrame
    final_title = json_response.get('query', {}).get('pages', [{}])[0].get('title', page_title)
    df['page'] = final_title
    if 'userid' in df.columns:
        df['userid'] = df['userid'].fillna(0).apply(lambda x:str(int(x)))
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].apply(lambda x:x.date())
        df['lag'] = df['timestamp'].diff()/pd.Timedelta(1,'s')
        df['age'] = (df['timestamp'] - df['timestamp'].min())/pd.Timedelta(1,'d')
    if 'size' in df.columns:
        df['diff'] = df['size'].diff()
    
    return df
    
def get_page_revisions_from_date(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1, start='2001-01-01',stop='today'):
    """Return page revisions within a date/time interval.

    Args:
        page_title (str): Page title on the target wiki.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects.
        start (str | datetime-like): Inclusive window start.
        stop (str | datetime-like): Inclusive window end.

    Returns:
        pandas.DataFrame: Revision metadata in chronological order, with
        computed helper fields where source columns are available.
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
    json_response = _get_json(url = query_url, params = query_params)

    # Add the temporary list to the parent list
    revision_list += response_to_revisions(json_response)

    # Loop for the rest of the revisions
    while True:

        # Newer versions of the API return paginated results this way
        if 'continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvcontinue'] = json_response['continue']['rvcontinue']
            json_response = _get_json(url = query_url, params = query_continue_params)
            revision_list += response_to_revisions(json_response)
        
        # Older versions of the API return paginated results this way
        elif 'query-continue' in json_response:
            query_continue_params = deepcopy(query_params)
            query_continue_params['rvstartid'] = json_response['query-continue']['revisions']['rvstartid']
            json_response = _get_json(url = query_url, params = query_continue_params)
            revision_list += response_to_revisions(json_response)
        
        # If there are no more revisions, stop
        else:
            break

    # Convert to a DataFrame
    df = pd.DataFrame(revision_list)

    # Add in some helpful fields to the DataFrame
    final_title = json_response.get('query', {}).get('pages', [{}])[0].get('title', page_title)
    df['page'] = final_title
    if 'userid' in df.columns:
        df['userid'] = df['userid'].fillna(0).apply(lambda x:str(int(x)))
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].apply(lambda x:x.date())
        df['lag'] = df['timestamp'].diff()/pd.Timedelta(1,'s')
        df['age'] = (df['timestamp'] - df['timestamp'].min())/pd.Timedelta(1,'d')
    if 'size' in df.columns:
        df['diff'] = df['size'].diff()

    return df
    
def chunks(l, n=50):
    """Yield fixed-size chunks from a list-like sequence.

    Args:
        l (list): Sequence to split into chunks.
        n (int): Chunk size.

    Yields:
        list: Consecutive slices of `l` up to length `n`.
    """
    for i in range(0, len(l), n):
        yield l[i:i + n]

def get_redirects_linking_here(page_title, endpoint="en.wikipedia.org/w/api.php", namespace=0):
    """Return redirect pages that link to a target page.

    Args:
        page_title (str): Target page title.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        namespace (int | str): Namespace filter for `linkshere`.

    Returns:
        list[str]: Redirect page titles that point to `page_title`.
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
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'linkshere' in json_response['query']['pages'][0]:
        subquery_lh_list = json_response['query']['pages'][0]['linkshere']
        lh_list += subquery_lh_list
    
        while True:

            if 'continue' not in json_response:
                break

            else:
                query_continue_params = deepcopy(query_params)
                query_continue_params['lhcontinue'] = json_response['continue']['lhcontinue']
                json_response = _get_json(url = query_url, params = query_continue_params)
                subquery_lh_list = json_response['query']['pages'][0]['linkshere']
                lh_list += subquery_lh_list
    
    return [i['title'] for i in lh_list]

def get_redirects_map(page_list, endpoint="en.wikipedia.org/w/api.php"):
    """Return redirect mappings for a list of page titles.

    Args:
        page_list (list[str]): Page titles to resolve.
        endpoint (str): MediaWiki `api.php` endpoint host/path.

    Returns:
        dict[str, str]: Mapping of redirect title -> canonical target title.
    """
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
        json_response = _get_json(url=query_url,params=query_params)
        
        if 'redirects' in json_response['query']:
            mapping = {redir['from']:redir['to'] for redir in json_response['query']['redirects']}
            redirects_d.update(mapping)
            
    return redirects_d
        

def resolve_redirects(page_list,endpoint="en.wikipedia.org/w/api.php"):
    """Resolve page titles to the titles returned by MediaWiki.

    Args:
        page_list (list[str]): Page titles to resolve.
        endpoint (str): MediaWiki `api.php` endpoint host/path.

    Returns:
        list[str]: Titles returned in API page order for each chunk.
    """
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
        json_response = _get_json(url=query_url,params=query_params)
        
        if 'pages' in json_response['query']:
            pages = [page['title'] for page in json_response['query']['pages']]
            resolved_page_list += pages
            
    return resolved_page_list

def get_page_raw_content(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Return parsed HTML content for the current page revision.

    Args:
        page_title (str): Page title.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects.

    Returns:
        str: HTML string from `action=parse`, or an empty string if unavailable.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'parse' in json_response.keys():
        markup = json_response['parse']['text']
        final_title = json_response['parse']['title']
    else:
        markup = str()
        final_title = page_title
    
    return markup

def parse_to_links(input,is_json=True):
    """Extract internal wiki-link titles from parsed HTML content.

    Args:
        input (dict | str): Parse JSON payload or raw HTML string.
        is_json (bool): Whether `input` is a parse JSON response.

    Returns:
        list[str]: Link titles in approximate document order (duplicates kept).
    """
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
        section_id = _extract_section_id(section)
        if section_id in bad_sections:

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
                if all(bad not in title for bad in bad_titles) and 'redlink' not in link.get('href', ''):
                    outlinks_list.append(title)

    # For each unordered list, extract the titles within the child links
    for unordered_list in soup.find_all('ul'):
        for item in unordered_list.find_all('li'):
            for link in item.find_all('a'):
                if link.has_attr('title'):
                    title = link['title']
                    # Ignore links that aren't interesting or are redlinks
                    if all(bad not in title for bad in bad_titles) and 'redlink' not in link.get('href', ''):
                        outlinks_list.append(title)
    
    return outlinks_list
        
def get_revision_raw_content(revid, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Return parsed HTML content for a specific revision id.

    Args:
        revid (int | str): Revision id.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Unused for revision lookups; kept for API compatibility.

    Returns:
        str: HTML string from `action=parse`, or an empty string if unavailable.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'parse' in json_response.keys():
        return json_response['parse']['text']
    else:
        return str()
    
def get_page_outlinks(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Return internal wiki-links for the current page revision.

    Args:
        page_title (str): Page title.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects.

    Returns:
        list[str]: Outlink titles extracted from parsed page HTML.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'parse' in json_response.keys():
        links = parse_to_links(json_response)
        final_title = json_response['parse']['title']
    else:
        links = list()
        final_title = page_title
        
    return links    
    
def get_revision_outlinks(revid, endpoint='en.wikipedia.org/w/api.php'):
    """Return internal wiki-links for a specific revision id.

    Args:
        revid (int | str): Revision id.
        endpoint (str): MediaWiki `api.php` endpoint host/path.

    Returns:
        list[str]: Outlink titles extracted from parsed revision HTML.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'parse' in json_response.keys():
        return parse_to_links(json_response)
    else:
        return list()
    
def get_page_externallinks(page_title, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Return external links from the current page revision.

    Args:
        page_title (str): Page title.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects.

    Returns:
        list[str]: External URLs from `action=parse`.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    links = list()
    if 'parse' in json_response.keys():
        if 'externallinks' in json_response['parse']:
            links = json_response['parse']['externallinks']
        
    return links
            
def get_revision_externallinks(revid, endpoint='en.wikipedia.org/w/api.php', redirects=1):
    """Return external links from a specific revision id.

    Args:
        revid (int | str): Revision id.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Unused for revision lookups; kept for API compatibility.

    Returns:
        list[str]: External URLs from `action=parse`.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    links = list()
    if 'parse' in json_response.keys():
        if 'externallinks' in json_response['parse']:
            links = json_response['parse']['externallinks']
        
    return links
        
def parse_to_text(input,is_json=True,parse_text=True):
    """Convert parsed HTML to paragraph text or paragraph HTML blocks.

    Args:
        input (dict | str): Parse JSON payload or raw HTML string.
        is_json (bool): Whether `input` is a parse JSON response.
        parse_text (bool): If True, return plain text with numeric citations removed.

    Returns:
        str: Newline-delimited paragraph content.
    """
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
        section_id = _extract_section_id(section)
        if section_id in bad_sections:

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
    """Return paragraph content for the current page revision.

    Args:
        page_title (str): Page title.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects.
        parsed_text (int | bool): True for plain text, False for paragraph HTML.

    Returns:
        str: Paragraph content, or an empty string if parsing fails.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'parse' in json_response.keys():
        return parse_to_text(json_response, parse_text=bool(parsed_text))
    return str()
    
    
def get_revision_content(revid,endpoint='en.wikipedia.org/w/api.php',parsed_text=1):
    """Return paragraph content for a specific revision id.

    Args:
        revid (int | str): Revision id.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        parsed_text (int | bool): True for plain text, False for paragraph HTML.

    Returns:
        str: Paragraph content, or an empty string if parsing fails.
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
    
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'parse' in json_response.keys():
        return parse_to_text(json_response, parse_text=bool(parsed_text))
    return str()
    
def get_page_redirects(page_list,endpoint='en.wikipedia.org/w/api.php'):
    """Return redirect targets for each input page title.

    Args:
        page_list (list[str]): Page titles to inspect.
        endpoint (str): MediaWiki `api.php` endpoint host/path.

    Returns:
        dict[str, str]: Mapping of original title -> resolved target title.
    """

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
        json_response = _get_json(url = query_url, params = query_params)

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
    """Return interlanguage page-title mappings for a page.

    Args:
        page_title (str): Source page title.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects.

    Returns:
        dict[str, str]: Mapping of language code -> localized title.
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
    json_response = _get_json(url=query_url,params=query_params)
    
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
    
def get_pageviews(page_title,endpoint='en.wikipedia.org',start='20150701',stop='today',useragent=None):
    """Return daily pageviews for a page via Wikimedia REST.

    Args:
        page_title (str): Page title.
        endpoint (str): Wikimedia project domain, for example `en.wikipedia.org`.
        start (str | datetime-like): Start date in `YYYYMMDD` or parseable format.
        stop (str | datetime-like): End date in `YYYYMMDD` or parseable format.
        useragent (str | None): Optional per-request `User-Agent` override.

    Returns:
        pandas.Series: Daily view counts indexed by timestamp.

    Raises:
        KeyError: If the REST payload does not include an `items` field.
    """
            
    quoted_page_title = quote(page_title, safe='')
    date_from = datetime.strftime(pd.to_datetime(start),'%Y%m%d')
    date_to = datetime.strftime(pd.to_datetime(stop),'%Y%m%d')
    
    #for access in ['all-access','desktop','mobile-app','mobile-web']:
    #for agent in ['all-agents','user','spider','bot']:
    s = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{1}/{2}/{3}/{0}/daily/{4}/{5}".format(quoted_page_title,endpoint,'all-access','user',date_from,date_to)
    effective_useragent = useragent if useragent else DEFAULT_USER_AGENT
    headers = {'User-Agent':effective_useragent}
    json_response = _get_json(s,headers=headers)
    
    if 'items' in json_response:
        df = pd.DataFrame(json_response['items'])
    else:
        raise KeyError('There is no "items" key in the JSON response.')
        
    df = df[['timestamp','views']]
    df['timestamp'] = pd.to_datetime(df['timestamp'],format='%Y%m%d%H')
    s = df.set_index('timestamp')['views']
        
    return s
    
def get_category_memberships(page_title,endpoint='en.wikipedia.org/w/api.php'):
    """Return category memberships for a page.

    Args:
        page_title (str): Page title.
        endpoint (str): MediaWiki `api.php` endpoint host/path.

    Returns:
        list[str]: Category titles (including `Category:` prefix).
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
    
    categories = list()
    json_response = _get_json(url=query_url,params=query_params)
    while True:
        if 'pages' in json_response['query']:
            if 'categories' in json_response['query']['pages'][0]:
                for category in json_response['query']['pages'][0]['categories']:
                    title = category['title']
                    categories.append(title)

        if 'continue' not in json_response:
            break

        query_continue_params = deepcopy(query_params)
        query_continue_params['clcontinue'] = json_response['continue']['clcontinue']
        json_response = _get_json(url=query_url, params=query_continue_params)
            
    return categories

def get_category_subcategories(category_title,endpoint='en.wikipedia.org/w/api.php'):
    """Return subcategories of a category.

    Args:
        category_title (str): Category name with or without `Category:` prefix.
        endpoint (str): MediaWiki `api.php` endpoint host/path.

    Returns:
        list[str]: Subcategory titles (including `Category:` prefix).
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
        
    members = list()
    json_response = _get_json(url = query_url, params = query_params)
    while True:
        if 'categorymembers' in json_response['query']:
            for member in json_response['query']['categorymembers']:
                members.append(member['title'])

        if 'continue' not in json_response:
            break

        query_continue_params = deepcopy(query_params)
        query_continue_params['cmcontinue'] = json_response['continue']['cmcontinue']
        json_response = _get_json(url = query_url, params = query_continue_params)
            
    return members

def get_category_members(category_title,depth=1,endpoint='en.wikipedia.org/w/api.php',namespace=0,prepend=True):
    """Return members of a category, optionally recursing into subcategories.

    Args:
        category_title (str): Category name with or without `Category:` prefix.
        depth (int): Recursion depth for traversing subcategories.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        namespace (int | str): Namespace filter passed to `cmnamespace`.
        prepend (bool): If True, prepend `Category:` when missing.

    Returns:
        list[str]: Member titles across the requested traversal depth.
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
        
    json_response = _get_json(url = query_url, params = query_params)

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
            json_response = _get_json(url = query_url, params = query_continue_params)
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
    """Return metadata for one or more users.

    Args:
        username_list (list[str]): Usernames to query.
        endpoint (str): MediaWiki `api.php` endpoint host/path.

    Returns:
        list[dict]: User metadata entries returned by `list=users`.
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
        
        json_response = _get_json(url = query_url, params = query_params)
        if 'query' in json_response:
            users_info += json_response['query']['users']
    
    return users_info

def get_user_contributions(username,endpoint='en.wikipedia.org/w/api.php', redirects=1,start='2001-01-01',stop='today'):
    """Return user contributions within a date/time interval.

    Args:
        username (str): Username to query.
        endpoint (str): MediaWiki `api.php` endpoint host/path.
        redirects (int | bool): Whether to resolve redirects on returned titles.
        start (str | datetime-like): Inclusive window start.
        stop (str | datetime-like): Inclusive window end.

    Returns:
        pandas.DataFrame: User contribution records with parsed timestamp/date
        fields when available.
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
    query_params['redirects'] = redirects
    query_params['formatversion'] = 2
    
    # Make the query
    json_response = _get_json(url = query_url, params = query_params)
    
    if 'query' in json_response:
        
        subquery_revision_list = json_response['query']['usercontribs']

        revision_list += subquery_revision_list

        while True:

            if 'continue' not in json_response:
                break

            else:
                query_continue_params = deepcopy(query_params)
                query_continue_params['uccontinue'] = json_response['continue']['uccontinue']
                json_response = _get_json(url = query_url, params = query_continue_params)
                subquery_revision_list = json_response['query']['usercontribs']
                revision_list += subquery_revision_list
                #time.sleep(1)
       
    df = pd.DataFrame(revision_list)
    
    if len(df.columns) > 0:
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].apply(lambda x:x.date())
        if 'userid' in df.columns:
            df['userid'] = df['userid'].fillna(0).apply(lambda x:str(int(x)))

    return df

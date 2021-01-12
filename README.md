# wikifunctions
These are Python 3 functions for retrieving data about revisions, content, pageviews, categories, and other data from the [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page). These functions have primarily been tested and used on the English Wikipedia API but can be extended to other MediaWiki APIs through the `endpoint` parameter for each function.

## Primary functions
* **get_all_page_revisions**: Takes a page title and returns a DataFrame of the revision history.  
* **get_page_revisions_from_date**: Takes a page title and return a DataFrame of revisions between the given dates.  
* **get_page_raw_content**: Takes a page title and returns the raw HTML of the current version.  
* **get_revision_raw_content**: Takes a revision ID and returns the raw HTML of the revision.  
* **get_page_outlinks**: Takes a page a title and returns a list of current links on the page.  
* **get_revision_outlinks**: Takes a revision ID and returns a list of links on the revision.
* **get_page_externallinks**: Takes a page title and returns a list of external links on the page.  
* **get_revision_externallinks**: Takes a revision ID and returns a list of external links on the revision.  
* **get_interlanguage_links**: Takes a page title and returns a dictionary of the page in other language editions.  
* **get_pageviews**: Takes a page title and returns the pageview data since July 2015.  
* **get_category_memberships**: Takes a page title and returns a list of categories of which the page is a member.  
* **get_category_subcategories**: Takes a category title and returns a list of sub-categories within the category.  
* **get_category_members**: Takes a category title and returns a list of pages within the category.  
* **get_user_info**: Takes a list of strings of usernames and returns a list of JSON objects of their information.  
* **get_user_contributions**: Takes a username and returns a list of their revisions/contributions between dates.  

## Helper functions
* **get_redirects_linking_here**: Takes a page title and returns a list of redirects linking to the page. Helpful for aggregating pageview data.  
* **get_redirects_map**: Takes a page title and returns a dictionary mapping the redirect page titles to the redirected page title. Helpful for aggregating pageview data.  
* **resolve_redirects**: Takes a list of strings and resolves them to their redirected page titles.  
* **parse_to_links**: Takes a json or string object and parses the body text into a list of hyperlinks.  
* **parse_to_text**: Takes a json or string object and parses the body text into plain text paragraphs.  

# Dependencies
The library uses pandas, datetime, BeautifulSoup, urllib, and requests.

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

## User-Agent requirement
All HTTP requests sent by this library include a `User-Agent` header by default.
Set `WIKIFUNCTIONS_USER_AGENT` to override it for your environment:

```bash
export WIKIFUNCTIONS_USER_AGENT="my-tool/1.0 (https://example.org/contact)"
```

## Examples

```python
import wikifunctions as wf
```

### Revision history for a page
```python
revs = wf.get_all_page_revisions("Python_(programming_language)")
print(revs[["revid", "timestamp", "user", "size"]].tail())
```

### Revisions between dates
```python
subset = wf.get_page_revisions_from_date(
    "Python_(programming_language)",
    start="2024-01-01",
    stop="2024-12-31",
)
print(len(subset))
```

### Use another MediaWiki project endpoint
```python
# French Wikipedia
fr_links = wf.get_page_outlinks(
    "Python_(langage)",
    endpoint="fr.wikipedia.org/w/api.php",
)
print(fr_links[:10])
```

### Aggregate pageviews across redirects
```python
title = "Python_(programming_language)"
redirects = wf.get_redirects_linking_here(title)
all_titles = [title] + redirects

series = []
for t in all_titles:
    s = wf.get_pageviews(t, endpoint="en.wikipedia.org")
    series.append(s.rename(t))

pv = series[0].to_frame().join(series[1:], how="outer").fillna(0)
pv["total_views"] = pv.sum(axis=1)
print(pv["total_views"].tail())
```

### Category membership and recursive category members
```python
cats = wf.get_category_memberships("Python_(programming_language)")
print(cats[:5])

members = wf.get_category_members("Programming_languages", depth=1)
print(members[:10])
```

### User metadata and contributions
```python
users = wf.get_user_info(["Example", "Jimbo Wales"])
print(users)

contribs = wf.get_user_contributions(
    "Jimbo Wales",
    start="2023-01-01",
    stop="2023-12-31",
)
print(contribs[["title", "timestamp", "sizediff"]].head())
```

## Endpoint conventions

- Most functions use the MediaWiki `api.php` endpoint format, for example: `en.wikipedia.org/w/api.php`.
- `get_pageviews` uses the Wikimedia REST project format, for example: `en.wikipedia.org`.
- You can switch projects by changing the language/domain portion of `endpoint`.

## Core Function Tutorials

### 1) Build a revision timeline
Use `get_all_page_revisions` for complete history and `get_page_revisions_from_date` for bounded windows.

```python
import wikifunctions as wf

revs = wf.get_all_page_revisions("Python_(programming_language)")
print(revs.columns)
print(revs[["timestamp", "user", "size", "diff"]].tail())

# Top editors by revision count
top_editors = revs["user"].value_counts().head(10)
print(top_editors)
```

```python
# Date-bounded slice for event windows
window = wf.get_page_revisions_from_date(
    "Python_(programming_language)",
    start="2024-01-01",
    stop="2024-06-30",
)
print(window[["timestamp", "user", "comment"]].head())
```

### 2) Retrieve raw HTML vs parsed text
Use raw functions when you need markup and parsed functions when you need plain text.

```python
html = wf.get_page_raw_content("Python_(programming_language)")
print(html[:500])  # raw parse HTML

text = wf.get_page_content("Python_(programming_language)", parsed_text=1)
print(text[:500])  # cleaned text paragraphs
```

```python
# Revision-specific content
revid = 1000000000
rev_html = wf.get_revision_raw_content(revid)
rev_text = wf.get_revision_content(revid, parsed_text=1)
print(len(rev_html), len(rev_text))
```

### 3) Extract internal and external links
Use outlink functions for wiki-to-wiki links and external-link functions for URLs.

```python
outlinks = wf.get_page_outlinks("Python_(programming_language)")
externals = wf.get_page_externallinks("Python_(programming_language)")

print("internal links:", len(outlinks))
print("external links:", len(externals))
print("sample external:", externals[:5])
```

```python
# Same operations for a specific revision
revid = 1000000000
rev_outlinks = wf.get_revision_outlinks(revid)
rev_externals = wf.get_revision_externallinks(revid)
print(len(rev_outlinks), len(rev_externals))
```

### 4) Map pages across languages
Use `get_interlanguage_links` to resolve titles across language editions.

```python
langlinks = wf.get_interlanguage_links("Python_(programming_language)")
print(langlinks.get("en"))
print(langlinks.get("fr"))
print(langlinks.get("de"))
```

### 5) Explore category graphs
Use category membership for a page, then expand into subcategories and members.

```python
cats = wf.get_category_memberships("Python_(programming_language)")
print(cats[:10])

subcats = wf.get_category_subcategories("Programming_languages")
print(subcats[:10])
```

```python
# Crawl one level deep under a category
members = wf.get_category_members("Programming_languages", depth=1)
print("member count:", len(members))
print(members[:20])
```

### 6) Analyze users and contributions
Use `get_user_info` for account metadata and `get_user_contributions` for edit activity.

```python
users = wf.get_user_info(["Example", "Jimbo Wales"])
for u in users:
    print(u.get("name"), u.get("editcount"), u.get("registration"))
```

```python
contribs = wf.get_user_contributions(
    "Jimbo Wales",
    start="2023-01-01",
    stop="2023-12-31",
)
print(contribs[["title", "timestamp", "sizediff"]].head())
print("edits:", len(contribs))
```

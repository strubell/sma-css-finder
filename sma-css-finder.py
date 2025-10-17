import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import re
from collections import deque

# Set page to wide mode for more space
st.set_page_config(layout="wide", page_title="CSS Finder")

st.title("SMA CSS Finder")

# Initialize session state for caching
if 'crawled_pages' not in st.session_state:
    st.session_state.crawled_pages = {}
if 'last_crawl_url' not in st.session_state:
    st.session_state.last_crawl_url = None
if 'selected_match' not in st.session_state:
    st.session_state.selected_match = None
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'current_search_class' not in st.session_state:
    st.session_state.current_search_class = None

# Add configuration options
max_pages = st.sidebar.number_input("Max pages to crawl", min_value=1, max_value=100, value=20)
same_domain_only = st.sidebar.checkbox("Only crawl same domain", value=True)

# Add cache control
if st.sidebar.button("Clear Cache"):
    st.session_state.crawled_pages = {}
    st.session_state.last_crawl_url = None
    st.sidebar.success("Cache cleared!")

# Show cache status
if st.session_state.crawled_pages:
    st.sidebar.info(f"📦 Cache contains {len(st.session_state.crawled_pages)} crawl(s)")

url = st.text_input("Enter website URL:", placeholder="https://example.com")

# Add search type selector
search_type = st.radio("Search for:", ["CSS Class", "ID"], horizontal=True)

if search_type == "CSS Class":
    search_value = st.text_input("Enter CSS class name:", placeholder="container", key="class_input")
    search_label = "class"
else:
    search_value = st.text_input("Enter ID:", placeholder="header", key="id_input")
    search_label = "ID"

if st.button("Find Instances"):
    if url and search_value:
        try:
            # Check if we need to crawl or can use cache
            cache_key = f"{url}_{max_pages}_{same_domain_only}"
            needs_crawl = (cache_key not in st.session_state.crawled_pages)
            
            if needs_crawl:
                st.info("🔄 Crawling site... (this will be cached for future searches)")
                
                # Parse the base URL
                base_parsed = urlparse(url)
                base_domain = f"{base_parsed.scheme}://{base_parsed.netloc}"
                
                # Initialize crawling
                visited = set()
                to_visit = deque([url])
                crawled_data = {}
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Crawl pages
                while to_visit and len(visited) < max_pages:
                    current_url = to_visit.popleft()
                    
                    # Remove fragment from URL
                    current_url, _ = urldefrag(current_url)
                    
                    if current_url in visited:
                        continue
                    
                    visited.add(current_url)
                    progress = len(visited) / max_pages
                    progress_bar.progress(min(progress, 1.0))
                    status_text.text(f"Crawling page {len(visited)}/{max_pages}: {current_url}")
                    
                    try:
                        # Fetch the page
                        response = requests.get(current_url, timeout=10)
                        response.raise_for_status()
                        
                        # Parse HTML
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Store all elements with classes for this page
                        all_elements_with_classes = soup.find_all(class_=True)
                        
                        crawled_data[current_url] = {
                            'soup': soup,
                            'elements': all_elements_with_classes
                        }
                        
                        # Find more links to crawl
                        if len(visited) < max_pages:
                            for link in soup.find_all('a', href=True):
                                next_url = urljoin(current_url, link['href'])
                                next_url, _ = urldefrag(next_url)
                                
                                # Filter based on domain if needed
                                if same_domain_only:
                                    next_parsed = urlparse(next_url)
                                    if next_parsed.netloc != base_parsed.netloc:
                                        continue
                                
                                # Only add HTTP(S) links
                                if next_url.startswith(('http://', 'https://')) and next_url not in visited:
                                    to_visit.append(next_url)
                    
                    except Exception as e:
                        st.warning(f"Error crawling {current_url}: {e}")
                
                progress_bar.empty()
                status_text.empty()
                
                # Cache the crawled data
                st.session_state.crawled_pages[cache_key] = crawled_data
                st.session_state.last_crawl_url = url
                st.success(f"✅ Crawled and cached {len(crawled_data)} pages")
            else:
                st.info(f"📦 Using cached data from previous crawl ({len(st.session_state.crawled_pages[cache_key])} pages)")
                crawled_data = st.session_state.crawled_pages[cache_key]
            
            # Search for the value in cached data
            st.info(f"🔍 Searching for {search_label} '{search_value}' in {len(crawled_data)} cached pages...")
            pages_with_matches = []
            
            for page_url, page_data in crawled_data.items():
                # Filter elements that have the specific class or ID
                if search_type == "CSS Class":
                    matching_elements = [el for el in page_data['elements'] if search_value in el.get('class', [])]
                else:  # ID
                    matching_elements = [el for el in page_data['elements'] if el.get('id') == search_value]
                
                if matching_elements:
                    pages_with_matches.append({
                        'url': page_url,
                        'elements': matching_elements,
                        'count': len(matching_elements)
                    })
            
            # Store results in session state
            st.session_state.search_results = {
                'pages_with_matches': pages_with_matches,
                'crawled_data': crawled_data,
                'search_value': search_value,
                'search_type': search_type
            }
            st.session_state.current_search_class = search_value
            
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Error fetching URL: {e}")
            st.info("Make sure the URL is correct and accessible")
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.exception(e)
    else:
        st.warning("Please enter both URL and search value")

# Display results from session state (persists across reruns)
if st.session_state.search_results:
    results = st.session_state.search_results
    pages_with_matches = results['pages_with_matches']
    crawled_data = results['crawled_data']
    search_value = results['search_value']
    search_type = results['search_type']
    
    if pages_with_matches:
        search_label = "class" if search_type == "CSS Class" else "ID"
        st.subheader(f"🎯 Found {search_label} '{search_value}' on {len(pages_with_matches)} page(s)")
        
        # Create two columns: results on left (wider), preview on right (wider)
        # Use full container width
        col_left, col_right = st.columns([1, 1.5])
        
        with col_left:
            st.markdown("### Matches")
            for page_idx, page in enumerate(pages_with_matches):
                with st.expander(f"📄 {page['url']} ({page['count']} instances)", expanded=(page_idx==0)):
                    st.markdown(f"**Page URL:** {page['url']}")
                    st.markdown(f"**Total instances:** {page['count']}")
                    
                    for i, element in enumerate(page['elements'], 1):
                        # Create a unique key for this match
                        match_key = f"{page['url']}_{i}"
                        
                        st.markdown(f"---\n**Instance {i}:**")
                        st.markdown(f"- Tag: `<{element.name}>`")
                        st.markdown(f"- All classes: `{' '.join(element.get('class', []))}`")
                        if element.get('id'):
                            st.markdown(f"- ID: `{element.get('id')}`")
                        
                        # Add button to preview this match
                        if st.button(f"👁️ Preview", key=f"preview_{match_key}"):
                            # Store serializable data with the actual HTML string for exact matching
                            st.session_state.selected_match = {
                                'url': page['url'],
                                'element_html': str(element),
                                'element_id': element.get('id'),
                                'element_classes': element.get('class', []),
                                'element_tag': element.name,
                                'instance': i,
                                'match_index': i - 1,  # 0-based index in the matches list
                            }
                            st.rerun()
                        
                        st.markdown("**HTML:**")
                        st.code(str(element)[:1000], language="html")
                        
                        if len(str(element)) > 1000:
                            st.caption("(truncated - showing first 1000 chars)")
                        
                        text_content = element.get_text(strip=True)
                        if text_content:
                            st.markdown("**Text content:**")
                            st.text(text_content[:300])
                            if len(text_content) > 300:
                                st.caption("(truncated - showing first 300 chars)")
        
        with col_right:
            st.markdown("### Page Preview")
            if st.session_state.selected_match:
                match_info = st.session_state.selected_match
                st.markdown(f"**Previewing:** {match_info['url']}")
                st.markdown(f"**Instance:** #{match_info['instance']}")
                
                # Get the page data from crawled_data
                page_url = match_info['url']
                if page_url in crawled_data:
                    try:
                        # Get the original soup and create a modified version with highlighting
                        soup_copy = BeautifulSoup(str(crawled_data[page_url]['soup']), 'html.parser')
                        
                        # Get the match index to find the exact element
                        match_index = match_info.get('match_index', 0)
                        element_classes = match_info.get('element_classes', [])
                        element_tag = match_info.get('element_tag')
                        element_html = match_info.get('element_html', '')
                        
                        # Find ALL matching elements with the same criteria
                        all_matching = soup_copy.find_all(element_tag, class_=element_classes)
                        
                        # Use the specific index to get the correct element
                        found_element = None
                        if all_matching and match_index < len(all_matching):
                            found_element = all_matching[match_index]
                        
                        if found_element:
                            # Add highlight class
                            if found_element.get('class'):
                                found_element['class'].append('highlight-match')
                            else:
                                found_element['class'] = ['highlight-match']
                            st.success(f"✓ Element #{match_info['instance']} found and will be highlighted")
                        else:
                            st.warning(f"⚠ Element to highlight not found in page (index: {match_index}, total matches: {len(all_matching)})")
                        
                        # Add custom CSS to highlight matched elements - yellow semi-transparent
                        # Add timestamp to ensure iframe refreshes
                        import time
                        timestamp = int(time.time() * 1000)
                        highlight_style = f"""
                        <style>
                        .highlight-match {{
                            background-color: rgba(255, 255, 0, 0.4) !important;
                            border: 8px dashed #ffcc00 !important;
                            scroll-margin-top: 100px;
                            box-shadow: 0 0 10px rgba(255, 204, 0, 0.6) !important;
                        }}
                        </style>
                        <script>
                        // Timestamp: {timestamp}
                        window.onload = function() {{
                            var elements = document.getElementsByClassName('highlight-match');
                            if (elements.length > 0) {{
                                elements[0].scrollIntoView({{behavior: 'smooth', block: 'center'}});
                            }}
                        }};
                        </script>
                        """
                        
                        modified_html = str(soup_copy)
                        
                        # Inject the style into the head
                        if '<head>' in modified_html:
                            modified_html = modified_html.replace('<head>', f'<head>{highlight_style}')
                        else:
                            modified_html = highlight_style + modified_html
                        
                        # Display the page in an iframe (no key parameter needed)
                        import streamlit.components.v1 as components
                        components.html(modified_html, height=800, scrolling=True)
                    except Exception as e:
                        st.error(f"Error rendering preview: {e}")
                        st.exception(e)
                else:
                    st.error("Page data not found in cache")
            else:
                st.info("👈 Click a 'Preview' button to see the page with the highlighted element")
    else:
        st.warning(f"⚠️ No instances of {search_label} '{search_value}' found on any of the pages")
    
    # Show all crawled URLs
    with st.expander(f"📋 All crawled URLs ({len(crawled_data)} total)"):
        for crawled_url in sorted(crawled_data.keys()):
            st.text(crawled_url)

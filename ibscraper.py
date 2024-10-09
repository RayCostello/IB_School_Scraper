#Go through HTML file and grab the id then go to the link school/id
#Create scraper that parses all data client wants
#Search for id and grab value next to it
#Search for "View more schools ({from}-{to})" use link above it to go to next page.
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from fake_useragent import UserAgent
from requests.exceptions import RequestException

def get_soup(url, session, retries=3):
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.ibo.org/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'DNT': '1',
    }

    for attempt in range(retries):
        try:
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except RequestException as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            time.sleep(5)
    print(f"Failed to fetch {url} after {retries} retries.")
    return None

def extract_school_ids(soup):
    if not soup:
        return []
    school_links = soup.select('a[href^="/school/"]')
    return [link['href'].split('/')[-2] for link in school_links]

def extract_next_page_url(soup):
    if not soup:
        return None
    
    # First, try the known pattern
    next_page = soup.find('a', class_='Button Button--widest', attrs={'data-module': 'load-more'})
    if next_page and 'href' in next_page.attrs:
        return next_page['href']

    # Alternative approach: Check for any link that looks like a "next page" button
    alt_next = soup.find('a', {'aria-label': 'Next page'})
    if alt_next and 'href' in alt_next.attrs:
        return alt_next['href']

    # Final fallback: Look for links that contain the word 'Next' (text-based)
    pagination_links = soup.find_all('a')
    for link in pagination_links:
        if 'next' in link.text.lower() and 'href' in link.attrs:
            return link['href']
    
    return None

def scrape_school_data(school_id, session):
    school_url = f"https://www.ibo.org/school/{school_id}/"
    soup = get_soup(school_url, session)
    
    if not soup:
        return None

    data = {'ID': school_id}

    # Extract school name
    school_name = soup.find('h1', class_='Heading Heading--blue Heading--h1 u-marginBottomL')
    if school_name:
        data['School name'] = school_name.text.strip()

    # Extract basic information
    property_list = soup.find('dl', class_='PropertyList')
    if property_list:
        for item in property_list.find_all('div', class_='PropertyList-item'):
            key = item.find('dt', class_='PropertyList-key').text.strip(':')
            value = item.find('dd', class_='PropertyList-value').text.strip()
            if key in ['Type', 'Head of school', 'IB School since', 'Country / territory', 'Region', 'IB School code']:
                data[key] = value

    # Extract website
    website = soup.find('a', class_='Link')
    if website:
        data['Website'] = website['href']

    # Extract diploma types
    diploma_types = []
    programme_sections = soup.find_all('h3')
    for section in programme_sections:
        img = section.find('img')
        if img and 'alt' in img.attrs:
            alt_text = img['alt'].upper()
            if alt_text in ['MYP', 'PYP', 'CP', 'DIPLOMA']:
                diploma_types.append(alt_text)
    data['Diploma types'] = ', '.join(diploma_types) if diploma_types else 'None found'

    # Initialize containers for storing multiple values across all programmes
    authorised_dates = []
    languages_of_instruction = []
    genders = []
    boarding_facilities = []
    examinations = []

    # Iterate over each diploma section to collect relevant data
    dp_info_elements = soup.find_all('div', class_='PropertyList u-marginTopZero')
    for dp_info in dp_info_elements:
        for item in dp_info.find_all('div', class_='PropertyList-item'):
            key = item.find('div', class_='PropertyList-key').text.strip(':')
            value = item.find('div', class_='PropertyList-value').text.strip()

            if key == 'Authorised':
                authorised_dates.append(value)
            elif key == 'Language of instruction':
                languages_of_instruction.append(value)
            elif key == 'Gender':
                genders.append(value)
            elif key == 'Boarding facilities':
                boarding_facilities.append(value)
            elif key == 'Examinations':
                examinations.append(value)

    # Insert concatenated values into the data dictionary
    if authorised_dates:
        data['Authorised'] = ', '.join(set(authorised_dates))
    if languages_of_instruction:
        data['Language of instruction'] = ', '.join(set(languages_of_instruction))
    if genders:
        data['Gender'] = ', '.join(set(genders))
    if boarding_facilities:
        data['Boarding facilities'] = ', '.join(set(boarding_facilities))
    if examinations:
        data['Examinations'] = ', '.join(set(examinations))

    # Extract subjects
    subjects = soup.find_all('li', class_='List-item u-xsm-size1of2')
    if subjects:
        data['Subjects offered'] = ', '.join([subject.text.strip() for subject in subjects])

    return data


def main():
    base_url = "https://www.ibo.org/programmes/find-an-ib-school/?SearchFields.Region=&SearchFields.Country=&SearchFields.Keywords=&SearchFields.Language=&SearchFields.BoardingFacilities=&SearchFields.SchoolGender="
    all_school_ids = []
    current_page_url = base_url
    page_number = 1

    session = requests.Session()

    while current_page_url:
        print(f"Fetching page {page_number}: {current_page_url}")
        soup = get_soup(current_page_url, session)
        if not soup:
            print(f"Failed to fetch {current_page_url}. Exiting loop.")
            break

        school_ids = extract_school_ids(soup)
        all_school_ids.extend(school_ids)

        print(f"Collected {len(school_ids)} school IDs from page {page_number}. Total: {len(all_school_ids)}")
        
        next_page_url = extract_next_page_url(soup)
        if next_page_url:
            if next_page_url.startswith('//'):
                current_page_url = f"https:{next_page_url}"
            elif next_page_url.startswith('/'):
                current_page_url = f"https://www.ibo.org{next_page_url}"
            else:
                current_page_url = next_page_url
            page_number += 1
        else:
            print("No more pages found. Ending pagination.")
            current_page_url = None
        
        time.sleep(random.uniform(3, 7))  # Random delay between requests

    print(f"Total number of school IDs collected: {len(all_school_ids)}")

    school_data = []
    for index, school_id in enumerate(all_school_ids, 1):
        print(f"Scraping school ID: {school_id} ({index}/{len(all_school_ids)})")
        data = scrape_school_data(school_id, session)
        if data:
            school_data.append(data)
        else:
            print(f"Failed to scrape data for school ID: {school_id}")
        time.sleep(random.uniform(2, 5))  # Random delay between requests

    df = pd.DataFrame(school_data)
    df.to_excel('ib_schools_detailed.xlsx', index=False)
    print("Data saved to ib_schools_detailed.xlsx")

if __name__ == "__main__":
    main()
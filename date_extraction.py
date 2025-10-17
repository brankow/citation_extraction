import re
from typing import Optional, Tuple
from datetime import datetime

class DateExtractor:
    # Month mappings for English, French, and German
    MONTHS = {
        # English
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        # English abbreviations
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        # French
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
        'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
        'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12,
        # French abbreviations
        'janv': 1, 'févr': 2, 'avr': 4, 'juil': 7,
        'déc': 12,
        # German
        'januar': 1, 'februar': 2, 'märz': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12,
        # German abbreviations
        'mär': 3, 'okt': 10, 'dez': 12,
    }
    
    CURRENT_YEAR = datetime.now().year
    MIN_YEAR = 1900

    # --- Precompiled regex patterns ---
    _MONTH_NAMES = '|'.join(MONTHS.keys())

    _PATTERNS = {
        "date_range": re.compile(r'\bto\b|\d+-\d+(?:\s+\w+\s+\d{4})', re.IGNORECASE),
        "invalid_year_format": re.compile(r'\b\d{4}-\d{7,}\b'),  # Like 2010-0024077
        "p1": re.compile(rf'\b(\d{{1,2}})\.?\s*({_MONTH_NAMES})\.?\s*(\d{{4}})\b', re.IGNORECASE),
        "p2_range": re.compile(rf'\b({_MONTH_NAMES})\s+\d+\s+to\s+\d+,\s+(\d{{4}})\b', re.IGNORECASE),
        "p2": re.compile(rf'\b({_MONTH_NAMES})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\.?\s*,?\s*(\d{{4}})', re.IGNORECASE),
        "p3": re.compile(rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\.?\s+(?:of\s+)?({_MONTH_NAMES})\s*,?\s*(\d{{4}})\b', re.IGNORECASE),
        "p4": re.compile(rf'\b(\d{{4}})[,\s]+({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:[;\s(]|$)', re.IGNORECASE),
        "p4_range": re.compile(rf'\b(\d{{4}})\s+({_MONTH_NAMES})\s+(\d{{1,2}})-({_MONTH_NAMES})', re.IGNORECASE),
        "p5": re.compile(rf'\b({_MONTH_NAMES})-({_MONTH_NAMES})\s+(\d{{4}})\b', re.IGNORECASE),
        "p6": re.compile(r'\b(\d{4})[.\s]+(\d{1,2})(?:\(|;|\.|$)'),
        "p7": re.compile(rf'\b(\d{{4}})\s*[.,]?\s*({_MONTH_NAMES})\b', re.IGNORECASE),
        "p8": re.compile(rf'\b({_MONTH_NAMES})\s*[.,]?\s*(\d{{4}})\b', re.IGNORECASE),
        "p9_ymd": re.compile(r'\b(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\b'),
        "p9_dmy": re.compile(r'\b(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})\b'),
        "p10": re.compile(r'\b(\d{4})-(\d{1,2})(?:\D|$)'),
        "year_any": re.compile(r'\b(\d{4})\b'),
        "year_range": re.compile(r'\b(\d{4})-(\d{4})\b'),
        "year_long": re.compile(r'\b(\d{4})-\d{5,}\b'),
        "year_paren": re.compile(r'\((\d{4})\)'),
        "year_bracket": re.compile(r'\[(\d{4})\]'),
    }
    
    @classmethod
    def _is_valid_year(cls, year: int) -> bool:
        """Check if year is within valid range."""
        return cls.MIN_YEAR <= year <= cls.CURRENT_YEAR
    
    @classmethod
    def _is_valid_day(cls, day: int, month: Optional[int] = None) -> bool:
        """Check if day is valid (1-31 range, basic check)."""
        return 1 <= day <= 31
    
    @classmethod
    def _is_valid_month(cls, month: int) -> bool:
        """Check if month is valid (1-12)."""
        return 1 <= month <= 12
    
    @classmethod
    def extract(cls, paragraph: str) -> str:
        """
        Extract date from paragraph and return in ddmmyyyy format.
        
        Returns:
            str: Date in ddmmyyyy format, or '00000000' if no valid date found
        """
        if not paragraph or paragraph.strip() in ['N/A', '', 'n/a']:
            return '00000000'
        
        # Early rejection: Check for invalid year formats like 2010-0024077
        if cls._PATTERNS["invalid_year_format"].search(paragraph):
            return '00000000'
        
        day, month, year = None, None, None
        
        # Check for date ranges that should be ignored for day extraction
        has_date_range = bool(cls._PATTERNS["date_range"].search(paragraph))
        
        # Priority 1: Day Month Year with period (e.g., "24 Okt. 2013", "20. Juni 2001")
        match = cls._PATTERNS["p1"].search(paragraph)
        if match:
            day_str, month_str, year_str = match.groups()
            potential_day = int(day_str)
            potential_month = cls.MONTHS.get(month_str.lower())
            potential_year = int(year_str)
            
            if cls._is_valid_year(potential_year):
                year = potential_year
                if potential_month and cls._is_valid_month(potential_month):
                    month = potential_month
                    if cls._is_valid_day(potential_day, month):
                        day = potential_day
        
        # Priority 2: Month Name Day, Year (e.g., "September, 30, 2021", "November 30th, 2022")
        if day is None and month is None and year is None:
            # Don't extract day if it's a range like "December 17 to 18"
            if has_date_range and cls._PATTERNS["p2_range"].search(paragraph):
                match = cls._PATTERNS["p2_range"].search(paragraph)
                if match:
                    month_str, year_str = match.groups()
                    potential_month = cls.MONTHS.get(month_str.lower())
                    potential_year = int(year_str)
                    if cls._is_valid_year(potential_year):
                        year = potential_year
            else:
                match = cls._PATTERNS["p2"].search(paragraph)
                if match:
                    month_str, day_str, year_str = match.groups()
                    potential_day = int(day_str)
                    potential_month = cls.MONTHS.get(month_str.lower())
                    potential_year = int(year_str)
                    
                    if cls._is_valid_year(potential_year):
                        year = potential_year
                        if potential_month and cls._is_valid_month(potential_month):
                            month = potential_month
                            if cls._is_valid_day(potential_day, month):
                                day = potential_day
        
        # Priority 3: Day Month Name Year (e.g., "15 January 2025", "1st. February 2025", "15th of March 2025")
        if day is None and month is None and year is None:
            match = cls._PATTERNS["p3"].search(paragraph)
            if match:
                day_str, month_str, year_str = match.groups()
                potential_day = int(day_str)
                potential_month = cls.MONTHS.get(month_str.lower())
                potential_year = int(year_str)
                
                if cls._is_valid_year(potential_year):
                    year = potential_year
                    if potential_month and cls._is_valid_month(potential_month):
                        month = potential_month
                        if cls._is_valid_day(potential_day, month):
                            day = potential_day
        
        # Priority 4: Year Month Day patterns with ranges (e.g., "2012 Mar 31-Apr 4")
        if day is None and month is None and year is None:
            match = cls._PATTERNS["p4_range"].search(paragraph)
            if match:
                year_str, month_str, day_str, _ = match.groups()
                potential_year = int(year_str)
                potential_month = cls.MONTHS.get(month_str.lower())
                potential_day = int(day_str)
                
                if cls._is_valid_year(potential_year):
                    year = potential_year
                    if potential_month and cls._is_valid_month(potential_month):
                        month = potential_month
                        if cls._is_valid_day(potential_day, month):
                            day = potential_day
        
        # Priority 4b: Year Month Day patterns (e.g., "2013 Dec 21", "2012 Mar 31", "2013, May 10")
        if day is None and month is None and year is None:
            match = cls._PATTERNS["p4"].search(paragraph)
            if match:
                year_str, month_str, day_str = match.groups()
                potential_year = int(year_str)
                potential_month = cls.MONTHS.get(month_str.lower())
                potential_day = int(day_str)
                
                if cls._is_valid_year(potential_year):
                    year = potential_year
                    if potential_month and cls._is_valid_month(potential_month):
                        month = potential_month
                        if cls._is_valid_day(potential_day, month):
                            day = potential_day
        
        # Priority 5: Year Month (no day) patterns with ranges like "Mar-Apr 2016"
        # For ranges, we should NOT extract any month (return year only)
        if month is None and year is None:
            match = cls._PATTERNS["p5"].search(paragraph)
            if match:
                year_str = match.group(3)
                potential_year = int(year_str)
                
                if cls._is_valid_year(potential_year):
                    year = potential_year
                    # Don't extract month for ranges - leave it as None
        
        # Priority 6: Year.Month.Issue patterns (e.g., "2011.01.086", "2017. 11(2)")
        if month is None and year is None:
            match = cls._PATTERNS["p6"].search(paragraph)
            if match:
                year_str, month_str = match.groups()
                potential_year = int(year_str)
                potential_month = int(month_str)
                
                if cls._is_valid_year(potential_year) and cls._is_valid_month(potential_month):
                    year = potential_year
                    month = potential_month
        
        # Priority 7: Year Month patterns (e.g., "2015 Mar", "März 2015", "Juin 2025")
        if month is None and year is None:
            match = cls._PATTERNS["p7"].search(paragraph)
            if match:
                year_str, month_str = match.groups()
                potential_year = int(year_str)
                potential_month = cls.MONTHS.get(month_str.lower())
                
                if cls._is_valid_year(potential_year):
                    year = potential_year
                    if potential_month and cls._is_valid_month(potential_month):
                        month = potential_month
        
        # Priority 8: Month Name Year (e.g., "Mai 2008", "March 1996")
        if month is None and year is None:
            match = cls._PATTERNS["p8"].search(paragraph)
            if match:
                month_str, year_str = match.groups()
                potential_month = cls.MONTHS.get(month_str.lower())
                potential_year = int(year_str)
                
                if cls._is_valid_year(potential_year):
                    year = potential_year
                    if potential_month and cls._is_valid_month(potential_month):
                        month = potential_month
        
        # Priority 9: Numeric dates with dots or dashes (dd.mm.yyyy, yyyy.mm.dd, dd-mm-yyyy)
        if day is None and month is None and year is None:
            # Try yyyy.mm.dd or yyyy.m.d format first
            match = cls._PATTERNS["p9_ymd"].search(paragraph)
            if match:
                first, second, third = match.groups()
                potential_year = int(first)
                potential_month = int(second)
                potential_day = int(third)
                
                if cls._is_valid_year(potential_year) and cls._is_valid_month(potential_month) and cls._is_valid_day(potential_day):
                    year = potential_year
                    month = potential_month
                    day = potential_day
            
            # Try dd.mm.yyyy or dd-mm-yyyy format
            if year is None:
                match = cls._PATTERNS["p9_dmy"].search(paragraph)
                if match:
                    first, second, third = match.groups()
                    potential_day = int(first)
                    potential_month = int(second)
                    potential_year = int(third)
                    
                    if cls._is_valid_year(potential_year):
                        year = potential_year
                        # Check if day is invalid (>31), reject the whole date
                        if potential_day > 31 or potential_month > 12:
                            return '00000000'
                        # Prefer day-month-year interpretation
                        if cls._is_valid_month(potential_month) and cls._is_valid_day(potential_day):
                            month = potential_month
                            day = potential_day
                        # Try month-day-year if above fails
                        elif cls._is_valid_month(potential_day) and cls._is_valid_day(potential_month):
                            month = potential_day
                            day = potential_month
                        # Only month valid
                        elif cls._is_valid_month(potential_month):
                            month = potential_month
                        elif cls._is_valid_month(potential_day):
                            month = potential_day
        
        # Priority 10: Year-Month format (yyyy-m or yyyy-mm) but NOT like yyyy-mmmmmmm
        if month is None and year is None:
            match = cls._PATTERNS["p10"].search(paragraph)
            if match:
                year_str, month_str = match.groups()
                potential_year = int(year_str)
                potential_month = int(month_str)
                
                # Only accept if month is 1-2 digits (not part of a longer number)
                if len(month_str) <= 2 and cls._is_valid_year(potential_year) and cls._is_valid_month(potential_month):
                    year = potential_year
                    month = potential_month
        
        # Priority 11: Extract latest year from texts like "Edition 2007, Issue 2015"
        if year is None:
            all_years = cls._PATTERNS["year_any"].findall(paragraph)
            valid_years = [int(y) for y in all_years if cls._is_valid_year(int(y))]
            if valid_years:
                year = max(valid_years)
        
        # Priority 12: Year ranges like "2001-2007", "1988-1999" - extract first year
        if year is None:
            match = cls._PATTERNS["year_range"].search(paragraph)
            if match:
                first_year, second_year = match.groups()
                first_year_int = int(first_year)
                second_year_int = int(second_year)
                
                if cls._is_valid_year(first_year_int) and cls._is_valid_year(second_year_int):
                    year = first_year_int
        
        # Priority 13: Year followed by large numbers like "2005-343699" - extract just year
        if year is None:
            match = cls._PATTERNS["year_long"].search(paragraph)
            if match:
                year_str = match.group(1)
                potential_year = int(year_str)
                if cls._is_valid_year(potential_year):
                    year = potential_year
        
        # Priority 14: Year in parentheses
        if year is None:
            matches = cls._PATTERNS["year_paren"].findall(paragraph)
            for match in matches:
                potential_year = int(match)
                if cls._is_valid_year(potential_year):
                    year = potential_year
                    break
        
        # Priority 15: Year in square brackets
        if year is None:
            match = cls._PATTERNS["year_bracket"].search(paragraph)
            if match:
                year_str = match.group(1)
                potential_year = int(year_str)
                if cls._is_valid_year(potential_year):
                    year = potential_year
        
        # If no valid date found, return all zeros
        if year is None:
            return '00000000'
        
        # Format output
        day_str = f'{day:02d}' if day else '00'
        month_str = f'{month:02d}' if month else '00'
        year_str = f'{year:04d}'
        
        return f'{day_str}{month_str}{year_str}'


# Example usage
if __name__ == '__main__':
    test_cases_collection = {
        "13-1-2025":"13012025",
        "1-13-2025":"13012025",
        "15 January 2025":"15012025",
        "1st. February 2025":"01022025",
        "September, 30, 2021":"30092021",
        "September 30, 2021":"30092021",
        "1st. February 2025 01-02-2025":"01022025",
        "January 1st., 2025":"01012025",
        "25 Okt 2025":"25102025",
        "Juin 2025":"00062025",
        "(2025)":"00002025",
        "The meeting is scheduled for 15th of March 2025.":"15032025",
        "Founded in October 2023.":"00102023",
        "Release date: 25.12.2024":"25122024",
        "1st January 2025":"01012025",
        "Release date: 01.32.2024": "00000000",
        "US 2024-0101":"00002024",
        "US 12024-0101":"00000000",
        "23 124801 (2020)":"00002020",
        "September 21-22, 1999":"00001999",
        "V18.1.2 (no date specified)":"00000000",
        "Nov. 30th, 2022FJT":"30112022",
        "2022.11.08":"08112022",
        "Nov. 30th, 2022(FJT-2022.11.08)":"30112022",
        "(2009)":"00002009",
        "16 juin 2007":"16062007",
        "v.14 MARCH 1996":"14031996",
        "17:804-807 (1999)":"00001999",
        "25(12):2516-2521 (1997)":"00001997",
        "9:142-148 (1990)":"00001990",
        "126:4550-4556":"00000000",
        "(2004)":"00002004",
        "Mai 2008":"00052008",
        "2010-0024077":"00000000",
        "(2011) Mar; 62(6)":"00002011",
        "2021 (revised)":"00002021",
        "as well as of chemicals presenting physical hazards according to the 'Globally Harmonized System of Classification and Labeling of Chemicals (GHS)'":"00000000",
        "Part III, Section 33.2 Flammable Solids 1.4' Rev 7, 2019":"00002019",
        "2017 16(3)":"00002017",
        "202 (1991)":"00001991",
        "2015 Mar; 12(3)":"00032015",
        "2013 Dec 21; 1(12)":"21122013",
        "Mar-Apr 2016":"00002016",
        "2020 Edition":"00002020",
        "2020 Jan-Dec":"00012020",
        "N/A":"00000000",
        "2017. 11(2)":"00112017",
        "2019-11-017, 2022-021, 2106-044-104":"00112019",
        "20 Dec 2019":"20122019",
        "2012 Mar 31-Apr 4":"31032012",
        "2013, May 10(5)":"10052013",
        "6. Aufl. Mai 2008":"00052008",
        "2013 Mar 83 (3)":"00032013",
        "EUROCRYPT 2001":"00002001",
        "2021;17(10)":"00002021",
        "2017 and 2018":"00002018",
        "doi:10.1002/mds.26125":"00000000",
        "2001 Oct 134(4)":"00102001",
        "23-30 April 2014":"30042014",
        "May-June 2003":"00062003",
        "12 Mar. 2014":"12032014",
        "2011.01.086":"00012011",
        "2020 12(11)":"00122020",
        "2005 26;4:3":"00002005",
        "2021 1;193:108631":"00012021",
        "2016 66(5):375-9":"00002016",
        "2022 6:947563":"00002022",
        "2007 98(2)":"00002007",
        "2016 20;8(1)":"00002016",
        "20220":"00000000",
        "2024-6":"00062024",
        "Sep. 1994 to Oct. 2011":"00091994",
        "15 JUN 2000":"15062000",
        "2009.3.31":"31032009",
        "2013, 13(8)":"00002013",
        "01.06.2007":"01062007",
        "11.10.2007":"11102007",
        "15 Feb 2019":"15022019",
        "24 Okt. 2013":"24102013",
        "1 Oct 2012":"01102012",
        "30.01.2018":"30012018",
        "März 2015":"00032015",
        "20. Juni 2001":"20062001",
        "24 Nov 2008":"24112008",
        "19 Mar 2015":"19032015",
        "29 Nov 2016":"29112016",
        "19 Jun 2019":"19062019",
        "1 Dec 2000":"01122000",
        "Edition 2007, Issue 2015":"00002015",
        "Amendment 2, 2013":"00002013",
        "Jul; 56(7):857-62 (1999)":"00001999",
        "2020 edition":"00002020",
        "2009 Sixth Edition":"00002009",
        "2005-343699":"00002005",
        "2001-2007":"00002007",
        "[2008]":"00002008",
        "Release of 24 May 2024":"24052024",
        "Release of 10 March 2024":"10032024",
        "June 2017, Revision 3":"00062017",
        "29.01.2019":"29012019",
        "2013, 2004":"00002013",
        "2009, 2010":"00002010",
        "(1966)":"00001966",
        "4th Edition":"00000000",
        "1996. 2016":"00002016",
        "(1984) 158:1018-1024":"00001984",
        "(1980) 14:399-445":"00001980",
        "(1998) 64:3932-3938":"00001998",
        "(1996) 250:734-741":"00001996",
        "2 March 2015 (2015-03-02)":"02032015",
        "25 September 2017 (2017-09-25)":"25092017",
        "9 September 2014 (2014-09-09)":"09092014",
        "December 17 to 18, 2022":"00002022",
        "ISO 23539:2005 (CIE S 010:2004)":"00002005",
        "2008-151773":"00002008",
        "1988-1999":"00001999",
        "Vol 365, Issue 24, p 4359-4391":"00000000",
    }
    
    issues = 0
    for test, result in test_cases_collection.items():
        detailed_reporting = False
        extracted_date = DateExtractor.extract(test)
        
        if extracted_date == result:
            if detailed_reporting:
                print(f'✅ {test} -> {result}')
        else:
            issues += 1
            print(f'❌  {test} -> {extracted_date if extracted_date else "None"} ≠ {result}')
    print("=" * 40)
    print(f'⭕ Total issues left : {issues} out of {len(test_cases_collection)}')
    print("=" * 40)
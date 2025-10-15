import re
from typing import Optional

class DateExtractor:
    # Month mappings for English, French, and German
    MONTHS = {
        # English
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        # English abbreviations
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        # French
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
        'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
        'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12,
        # French abbreviations
        'janv': 1, 'févr': 2, 'avr': 4, 'juil': 7,
        'sept': 9, 'oct': 10, 'nov': 11, 'déc': 12,
        # German
        'januar': 1, 'februar': 2, 'märz': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12,
        # German abbreviations
        'jan': 1, 'feb': 2, 'mär': 3, 'apr': 4,
        'mai': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'okt': 10, 'nov': 11, 'dez': 12,
    }
    
    # Precompiled regex patterns
    PATTERNS = {}
    
    @classmethod
    def _build_patterns(cls):
        """Build and precompile all regex patterns."""
        if cls.PATTERNS:
            return
        
        # Day with optional suffix (st, nd, rd, th) and optional punctuation
        day_with_suffix = r'(\d{1,2})(?:st|nd|rd|th)?\.?'
        month_names = '|'.join(cls.MONTHS.keys())
        month_pattern = f'({month_names})'
        year_pattern = r'(\d{4})'
        
        # Optional whitespace and punctuation
        sep = r'[\s,.\-]*'
        
        # Pattern 1: Day-Month-Year (13-1-2025 or 15 January 2025)
        cls.PATTERNS['day_month_year'] = re.compile(
            f'{day_with_suffix}{sep}{month_pattern}{sep}{year_pattern}',
            re.IGNORECASE
        )
        
        # Pattern 2: Month-Day-Year (1-13-2025 or January 1st., 2025)
        cls.PATTERNS['month_day_year'] = re.compile(
            f'{month_pattern}{sep}{day_with_suffix}{sep}{year_pattern}',
            re.IGNORECASE
        )
        
        # Pattern 3: Month-Year only (Juin 2025, 25 Okt 2025 without day)
        cls.PATTERNS['month_year'] = re.compile(
            f'{month_pattern}{sep}{year_pattern}',
            re.IGNORECASE
        )
        
        # Pattern 4: Year only in parentheses or standalone (2025)
        cls.PATTERNS['year_only'] = re.compile(
            f'\\(?{year_pattern}\\)?'
        )
        
        # Pattern 5: Numeric month-day or day-month (1-13 or 13-1)
        # This pattern ensures we match complete numeric date groups
        cls.PATTERNS['numeric_date'] = re.compile(
            f'(\d{{1,2}}){sep}(\d{{1,2}}){sep}{year_pattern}'
        )
    
    @classmethod
    def _validate_date(cls, day: Optional[int], month: Optional[int], year: Optional[int]) -> bool:
        """
        Validate that day and month are within valid ranges.
        
        Returns:
            bool: True if date is valid, False otherwise
        """
        if month is not None and (month < 1 or month > 12):
            return False
        if day is not None and (day < 1 or day > 31):
            return False
        return True
    
    @classmethod
    def extract(cls, paragraph: str) -> str:
        """
        Extract date from paragraph and return in ddmmyyyy format.
        
        Returns:
            str: Date in ddmmyyyy format, or empty string if no valid date found
        """
        cls._build_patterns()
        
        day, month, year = None, None, None
        date_extraction_attempted = False
        
        # Try numeric date patterns first (day-month-year preferred over month-day-year)
        match = cls.PATTERNS['numeric_date'].search(paragraph)
        if match:
            date_extraction_attempted = True
            first, second, year_str = match.groups()
            first_val, second_val = int(first), int(second)
            year = int(year_str)
            
            # Prefer day-month-year (day 1-31, month 1-12)
            if 1 <= first_val <= 31 and 1 <= second_val <= 12:
                day, month = first_val, second_val
            # Otherwise try month-day-year
            elif 1 <= second_val <= 31 and 1 <= first_val <= 12:
                day, month = second_val, first_val
            # If month is invalid, swap day and month (only if resulting month is valid)
            elif second_val > 12 and 1 <= first_val <= 12:
                if 1 <= second_val <= 31:  # Validate day after swap
                    day, month = second_val, first_val
                else:
                    # Swap didn't work - reject
                    return ''
            elif first_val > 12 and 1 <= second_val <= 12:
                if 1 <= first_val <= 31:  # Validate day after swap
                    day, month = first_val, second_val
                else:
                    # Swap didn't work - reject
                    return ''
            else:
                # No valid interpretation found - reject the whole match
                return ''
        
        # Try day-month-year with month names
        if day is None and month is None and year is None:
            match = cls.PATTERNS['day_month_year'].search(paragraph)
            if match:
                date_extraction_attempted = True
                day_str, month_str, year_str = match.groups()
                day = int(day_str)
                month = cls.MONTHS.get(month_str.lower())
                year = int(year_str)
        
        # Try month-day-year with month names
        if day is None and month is None and year is None:
            match = cls.PATTERNS['month_day_year'].search(paragraph)
            if match:
                date_extraction_attempted = True
                month_str, day_str, year_str = match.groups()
                day = int(day_str)
                month = cls.MONTHS.get(month_str.lower())
                year = int(year_str)
        
        # Try month-year only
        if month is None and year is None:
            match = cls.PATTERNS['month_year'].search(paragraph)
            if match:
                date_extraction_attempted = True
                month_str, year_str = match.groups()
                month = cls.MONTHS.get(month_str.lower())
                year = int(year_str)
                day = None
        
        # Try year only as last resort (only if no date extraction was attempted)
        if year is None and not date_extraction_attempted:
            match = cls.PATTERNS['year_only'].search(paragraph)
            if match:
                year_str = match.group(1)
                year = int(year_str)
        
        # Validate extracted date: if day or month were extracted, they must be valid
        if (day is not None or month is not None) and not cls._validate_date(day, month, year):
            return ''
        
        # Format output
        day_str = f'{day:02d}' if day else '00'
        month_str = f'{month:02d}' if month else '00'
        year_str = f'{year:04d}' if year else ''
        
        return f'{day_str}{month_str}{year_str}'


# Example usage
if __name__ == '__main__':
    test_cases = [
        'The meeting is scheduled for 15th of March 2025.',
        '23 124801 (2020)',
        'November 10, 2022',
        'September 21-22, 1999',
        '2022.11.08',
        '25(12):2516-2521 (1997)',
        '2010-0024077',
        '2015 Mar; 12(3)',
        '2012 Dec 21; 1(12)',
        'Mar-Apr 2016',
        '2020 Edition',
        '2020 Jan-Dec',
        '2020 Jan-Dec',
        'N/A',
        '2017. 11(2)',
        '2012 Mar 31-Apr 4',
        '2013, May 10(5)',
        '2013 Mar 83 (3)',
        '2001 Oct 134(4)',
        'May-June 2003',
        '12 Mar. 2014',
        '2017 and 2018',
        'doi:10.1002/mds.26125',
        '2001 Oct 134(4)',
        '23-30 April 2014',
        '2011.01.086',
        '2021 1;193:108631',
        '2022 6:947563',
        '20220',
        '2024-6',
        '2018-6',
        '2009.3.31',
        '2005-343699',
        '2001-2007',
        '2013, 2004',
        '2009, 2010',
        '1996. 2016',
        '(1984) 158:1018-1024',
        '(1998) 64:3932-3938',
        'December 17 to 18, 2022',
        'ISO 23539:2005 (CIE S 010:2004)',
        '2008-151773',
        '1988-1999',
        'September, 30, 2021',
        'September 30, 2021'
    ]

    rest_cases = [
            '13-1-2025',      # day-month-year (13 > 12, so day-month)
            '1-13-2025',      # month-day-year (13 > 12, so swap)
            '15 January 2025',
            '1st. February 2025',
            'September, 30, 2021',
            'September 30, 2021',
            '1st. February 2025 01-02-2025',
            'January 1st., 2025',
            '25 Okt 2025',
            'Juin 2025',
            '(2025)',
            'The meeting is scheduled for 15th of March 2025.',
            'Founded in October 2023.',
            'Release date: 25.12.2024',
            '1st January 2025',
            'Release date: 01.32.2024',  # Invalid: day 32
            'US 2024-0101',  # Invalid: should not extract
            'US 12024-0101',  # Invalid: should not extract
            '23 124801 (2020)',
    'September 21-22, 1999',
    'V18.1.2 (no date specified)',
    'Nov. 30th, 2022FJT',
    '2022.11.08',
    'Nov. 30th, 2022(FJT-2022.11.08)',
    '(2009)',
    '16 juin 2007',
    'v.14 MARCH 1996',
    '17:804-807 (1999)',
    '25(12):2516-2521 (1997)',
    '9:142-148 (1990)',
    '126:4550-4556',
    '(2004)',
    '(1970)',
    '(1961)',
    '(1975)',
    'Mai 2008',
    '2010-0024077',
    '(2009)',
    '(2017)',
    '(2002)',
    '(2007)',
    '(2000)',
    '(1975)',
    '(1985)',
    '(2011) Mar; 62(6)',
    '(2024)',
    '2021 (revised)',
    'as well as of chemicals presenting physical hazards according to the "Globally Harmonized System of Classification and Labeling of Chemicals (GHS)"',
    'Part III, Section 33.2 Flammable Solids1.4" Rev 7, 2019',
    '(2020)',
    '2017 16(3)',
    '(2005)',
    '(2014)',
    '202 (1991)',
    '(2010)',
    '(2008)',
    '(2015)',
    '2015 Mar; 12(3)',
    '2012 Dec 21; 1(12)',
    'Mar-Apr 2016',
    '2020 Edition',
    '2020 Jan-Dec',
    '2020 Jan-Dec',
    '(1983)',
    '(1987)',
    '(2001)',
    '(1996)',
    '(1993)',
    'N/A',
    '(1987)',
    '2017. 11(2)',
    '2019-11-017, 2022-021, 2106-044-104',
    '20 Dec 2019',
    '2012 Mar 31-Apr 4',
    '2013, May 10(5)',
    '6. Aufl. Mai 2008',
    '(1987)',
    '(1991)',
    '(1995)',
    '(1996)',
    '2013 Mar 83 (3)',
    'EUROCRYPT 2001',
    '2021;17(10)',
    '2017 and 2018',
    'doi:10.1002/mds.26125',
    '2001 Oct 134(4)',
    '23-30 April 2014',
    'May-June 2003',
    '(1995)',
    '(1995)',
    '12 Mar. 2014',
    '2017 and 2018',
    'doi:10.1002/mds.26125',
    '2001 Oct 134(4)',
    '23-30 April 2014',
    'May-June 2003',
    '(1995)',
    '12 Mar. 2014',
    '2011.01.086',
    '2020 12(11)',
    '2005 26;4:3',
    '2021 1;193:108631',
    '2016 66(5):375-9',
    '2022 6:947563',
    '2007 98(2)',
    '2016 20;8(1)',
    '2016 20;8(1)',
    '20220',
    '2024-6',
    '2018-6',
    'Sep. 1994 to Oct. 2011',
    '15 JUN 2000',
    '2009.3.31',
    '2013, 13(8)',
    '01.06.2007',
    '11.10.2007',
    '15 Feb 2019',
    '24 Okt. 2013',
    '1 Oct 2012',
    '30.01.2018',
    '(2019)',
    'März 2015',
    '15 Feb 2019',
    '20. Juni 2001',
    '20. Juni 2001',
    '15 Feb 2019',
    '30.01.2018',
    '(2017)',
    '(2019)',
    '(2005)',
    '01.06.2007',
    '11.10.2007',
    '15 Feb 2019',
    '24 Okt. 2013',
    '24 Nov 2008',
    '19 Mar 2015',
    '29 Nov 2016',
    '19 Jun 2019',
    '11 Jun 2019',
    '1 Dec 2000',
    'Edition 2007, Issue 2015',
    'Edition 2007, Issue 2015',
    'Amendment 2, 2013',
    'Jul; 56(7):857-62 (1999)',
    '(2015)',
    '2020 edition',
    '2009 Sixth Edition',
    '2005-343699',
    '2001-2007',
    '[2008]',
    'Release of 24 May 2024',
    'Release of 10 March 2024',
    'Release of 24 May 2024',
    '(1995)',
    'June 2017, Revision 3',
    '29.01.2019',
    '29.01.2019',
    '2013, 2004',
    '2009, 2010',
    '(1966)',
    '4th Edition',
    '1996. 2016',
    '(1984) 158:1018-1024',
    '(1980) 14:399-445',
    '(1998) 64:3932-3938',
    '(1996) 250:734-741',
    '2 March 2015 (2015-03-02)',
    '25 September 2017 (2017-09-25)',
    '9 September 2014 (2014-09-09)',
    'December 17 to 18, 2022',
    'ISO 23539:2005 (CIE S 010:2004)',
    '2008-151773',
    '1988-1999',
    'Vol 365, Issue 24, p 4359-4391',
        ]
    
    for test in test_cases:
        result = DateExtractor.extract(test)
        print(f'{test:50} -> {result}')
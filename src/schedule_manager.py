"""Schedule manager for padel visits with Russian date/time parsing."""

import re
from datetime import datetime, timezone, timedelta
import dataclasses
from typing import List, Dict, Optional, Tuple
import logging
import hashlib

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Visit:
    id: str
    start_time: datetime
    end_time: datetime
    original_text: str
    created_at: datetime
    
    def __hash__(self):
        # Hash based on start_time and end_time (ignore text variations)
        return hash((self.start_time, self.end_time))
    
    def __eq__(self, other):
        if not isinstance(other, Visit):
            return False
        # Consider visits equal if they have same start and end time
        return self.start_time == other.start_time and self.end_time == other.end_time


class ScheduleManager:
    """Manages padel visit schedules with Russian date/time parsing."""
    
    def __init__(self):
        self.visits = set()  # In-memory storage as set to prevent duplicates
        
        # Russian month names mapping
        self.russian_months = {
            'января': 1, 'январь': 1,
            'февраля': 2, 'февраль': 2,
            'марта': 3, 'март': 3,
            'апреля': 4, 'апрель': 4,
            'мая': 5, 'май': 5,
            'июня': 6, 'июнь': 6,
            'июля': 7, 'июль': 7,
            'августа': 8, 'август': 8,
            'сентября': 9, 'сентябрь': 9,
            'октября': 10, 'октябрь': 10,
            'ноября': 11, 'ноябрь': 11,
            'декабря': 12, 'декабрь': 12
        }
        
        # Russian weekday names mapping
        self.russian_weekdays = {
            'понедельник': 0, 'понедельника': 0, 'пн': 0,
            'вторник': 1, 'вторника': 1, 'вт': 1,
            'среда': 2, 'среду': 2, 'среды': 2, 'ср': 2,
            'четверг': 3, 'четверга': 3, 'чт': 3,
            'пятница': 4, 'пятницу': 4, 'пятницы': 4, 'пт': 4,
            'суббота': 5, 'субботу': 5, 'субботы': 5, 'сб': 5,
            'воскресенье': 6, 'воскресенья': 6, 'вс': 6
        }
        
        # Relative date keywords
        self.relative_dates = {
            'сегодня': 0,
            'завтра': 1,
            'послезавтра': 2
        }
        
        # Moscow timezone
        self.moscow_tz = timezone(timedelta(hours=3))
    
    def parse_weekday_date(self, text: str) -> Optional[datetime]:
        """Parse weekday names like 'понедельник' -> next Monday."""
        text_lower = text.lower()
        
        # Look for weekday names in the text
        for weekday_name, weekday_num in self.russian_weekdays.items():
            if weekday_name in text_lower:
                now = datetime.now(self.moscow_tz)
                current_weekday = now.weekday()
                
                # Calculate days until next occurrence of this weekday
                days_ahead = (weekday_num - current_weekday) % 7
                if days_ahead == 0:  # Today is the target weekday
                    days_ahead = 7  # Move to next week
                
                target_date = now + timedelta(days=days_ahead)
                return target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return None
    
    def parse_relative_date(self, text: str) -> Optional[datetime]:
        """Parse relative dates like 'сегодня', 'завтра', 'послезавтра'."""
        text_lower = text.lower()
        
        for relative_keyword, days_ahead in self.relative_dates.items():
            if relative_keyword in text_lower:
                now = datetime.now(self.moscow_tz)
                target_date = now + timedelta(days=days_ahead)
                return target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return None
    
    def parse_date_without_year(self, text: str) -> Optional[datetime]:
        """Parse date without year like '12 июля'."""
        # Pattern: number + russian month (no year)
        pattern = r'(\d{1,2})\s+([а-яё]+)(?!\s+\d{4})'
        match = re.search(pattern, text.lower())
        
        if not match:
            return None
            
        day = int(match.group(1))
        month_name = match.group(2)
        
        month = self.russian_months.get(month_name)
        if not month:
            return None
            
        now = datetime.now(self.moscow_tz)
        current_year = now.year
        
        try:
            # Try current year first
            target_date = datetime(current_year, month, day, tzinfo=self.moscow_tz)
            
            # If the date has passed, use next year
            if target_date.date() < now.date():
                target_date = datetime(current_year + 1, month, day, tzinfo=self.moscow_tz)
            
            return target_date
        except ValueError:
            return None
    
    def parse_russian_date(self, text: str) -> Optional[datetime]:
        """Parse Russian date format like '12 июля 2025'."""
        # Pattern: number + russian month + year
        pattern = r'(\d{1,2})\s+([а-яё]+)\s+(\d{4})'
        match = re.search(pattern, text.lower())
        
        if not match:
            return None
            
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        
        month = self.russian_months.get(month_name)
        if not month:
            return None
            
        try:
            return datetime(year, month, day, tzinfo=self.moscow_tz)
        except ValueError:
            return None
    
    def parse_time_range(self, text: str) -> Optional[Tuple[datetime, datetime]]:
        """Parse various time range formats."""
        text_lower = text.lower()
        
        # Pattern 1: (с|от)? HH:MM до HH:MM - unified pattern for all "до" formats
        pattern_do = r'(?:с|от)?\s*(\d{1,2})[:\.](\d{2})\s+до\s+(\d{1,2})[:\.](\d{2})'
        match_do = re.search(pattern_do, text_lower)
        if match_do:
            return self._create_time_range(match_do.group(1), match_do.group(2), match_do.group(3), match_do.group(4))
        
        # Pattern 2: HH-HH (short format)
        pattern_short = r'(\d{1,2})-(\d{1,2})(?!\d)'
        match_short = re.search(pattern_short, text_lower)
        if match_short:
            return self._create_time_range(match_short.group(1), "00", match_short.group(2), "00")
        
        # Pattern 3: HH:MM-HH:MM (dash format)
        pattern_dash = r'(\d{1,2})[:\.](\d{2})-(\d{1,2})[:\.](\d{2})'
        match_dash = re.search(pattern_dash, text_lower)
        if match_dash:
            return self._create_time_range(match_dash.group(1), match_dash.group(2), match_dash.group(3), match_dash.group(4))
        
        # Pattern 4: Single time - assume 1 hour duration
        single_time = self._parse_single_time(text_lower)
        if single_time:
            start_hour, start_minute = single_time
            end_hour = start_hour + 1
            end_minute = start_minute
            
            # Handle hour overflow
            if end_hour >= 24:
                end_hour = 23
                end_minute = 59
            
            return self._create_time_range(str(start_hour), str(start_minute), str(end_hour), str(end_minute))
        
        return None
    
    def _create_time_range(self, start_hour: str, start_minute: str, end_hour: str, end_minute: str) -> Optional[Tuple[datetime, datetime]]:
        """Helper method to create time range objects."""
        try:
            start_h = int(start_hour)
            start_m = int(start_minute)
            end_h = int(end_hour)
            end_m = int(end_minute)
            
            # Validate time ranges
            if not (0 <= start_h <= 23 and 0 <= start_m <= 59 and 0 <= end_h <= 23 and 0 <= end_m <= 59):
                return None
            
            start_time = datetime.min.replace(hour=start_h, minute=start_m)
            end_time = datetime.min.replace(hour=end_h, minute=end_m)
            return start_time, end_time
        except ValueError:
            return None
    
    def _parse_single_time(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse single time formats like 'в 16:00', 'в 16', '16:00'."""
        # Pattern 1: в HH:MM
        pattern1 = r'в\s+(\d{1,2})[:\.](\d{2})'
        match1 = re.search(pattern1, text)
        if match1:
            return int(match1.group(1)), int(match1.group(2))
        
        # Pattern 2: в HH (no minutes)
        pattern2 = r'в\s+(\d{1,2})(?![:\.])'
        match2 = re.search(pattern2, text)
        if match2:
            return int(match2.group(1)), 0
        
        # Pattern 3: время HH:MM
        pattern3 = r'время\s+(\d{1,2})[:\.](\d{2})'
        match3 = re.search(pattern3, text)
        if match3:
            return int(match3.group(1)), int(match3.group(2))
        
        # Pattern 4: HH:MM (standalone)
        pattern4 = r'(?<!\d)(\d{1,2})[:\.](\d{2})(?!\s*[-до])'
        match4 = re.search(pattern4, text)
        if match4:
            hour = int(match4.group(1))
            minute = int(match4.group(2))
            # Only accept if it looks like a reasonable time
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
        
        return None
    
    def parse_visit_info(self, text: str) -> Optional[Dict]:
        """Parse visit information from Russian text."""
        # Try different date parsing methods in order of preference
        date = None
        
        # 1. Try full date with year (12 июля 2025)
        date = self.parse_russian_date(text)
        
        # 2. Try weekday names (понедельник, вторник)
        if not date:
            date = self.parse_weekday_date(text)
        
        # 3. Try relative dates (сегодня, завтра)
        if not date:
            date = self.parse_relative_date(text)
        
        # 4. Try date without year (12 июля)
        if not date:
            date = self.parse_date_without_year(text)
        
        # Parse time range
        time_range = self.parse_time_range(text)
        
        if not date or not time_range:
            return None
            
        start_time, end_time = time_range
        
        # Combine date with times
        visit_start = date.replace(
            hour=start_time.hour,
            minute=start_time.minute,
            second=0,
            microsecond=0
        )
        
        visit_end = date.replace(
            hour=end_time.hour,
            minute=end_time.minute,
            second=0,
            microsecond=0
        )
        
        return {
            'date': date.date(),
            'start_time': visit_start,
            'end_time': visit_end,
            'original_text': text
        }
    
    def add_visit(self, text: str) -> Optional[Visit]:
        """Add a visit from parsed text."""
        visit_info = self.parse_visit_info(text)
        
        if not visit_info:
            return None
            
        # Create hash from start_time, end_time, and original_text
        hash_content = f"{visit_info['start_time'].isoformat()}_{visit_info['end_time'].isoformat()}_{text}"
        visit_id = hashlib.sha256(hash_content.encode()).hexdigest()
        
        visit = Visit(
            id=visit_id,
            start_time=visit_info['start_time'],
            end_time=visit_info['end_time'],
            original_text=text,
            created_at=datetime.now(self.moscow_tz)
        )
        
        # Check if visit already exists (based on start_time and end_time)
        if visit in self.visits:
            logger.info(f"Duplicate visit detected: {visit.start_time.strftime('%d.%m.%Y')} {visit.start_time.strftime('%H:%M')}-{visit.end_time.strftime('%H:%M')}")
            return None
        
        self.visits.add(visit)
        logger.info(f"Added visit: {visit.start_time.strftime('%d.%m.%Y')} {visit.start_time.strftime('%H:%M')}-{visit.end_time.strftime('%H:%M')}")
        
        return visit
    
    def cleanup_past_visits(self):
        """Remove visits that have already ended."""
        now = datetime.now(self.moscow_tz)
        before_count = len(self.visits)
        
        # Keep only visits that haven't ended yet
        self.visits = {
            visit for visit in self.visits
            if visit.end_time > now
        }
        
        removed_count = before_count - len(self.visits)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} past visit(s)")
    
    def get_upcoming_visits(self, days_ahead: int = 30) -> List[Visit]:
        """Get upcoming visits sorted by date/time."""
        # Clean up past visits first
        self.cleanup_past_visits()
        
        now = datetime.now(self.moscow_tz)
        cutoff = now + timedelta(days=days_ahead)
        
        upcoming = [
            visit for visit in self.visits
            if visit.start_time >= now and visit.start_time <= cutoff
        ]
        
        # Sort by start time
        upcoming.sort(key=lambda x: x.start_time)
        
        return upcoming
    
    def format_visit_list(self, visits: List[Visit]) -> str:
        """Format visits as a nice table for telegram."""
        if not visits:
            return "🎾 Нет запланированных визитов"
            
        lines = ["🎾 **Запланированные визиты:**", ""]
        
        for visit in visits:
            date_str = visit.start_time.strftime('%d.%m.%Y')
            time_str = f"{visit.start_time.strftime('%H:%M')}-{visit.end_time.strftime('%H:%M')}"
            
            lines.append(f"📅 **{date_str}** в **{time_str}**")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_visit_count(self) -> int:
        """Get total number of visits."""
        return len(self.visits) 
import calendar
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def build_calendar(year, month):
    markup = [[InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore")]]
    markup.append([InlineKeyboardButton(d, callback_data="ignore") for d in ["Mo","Tu","We","Th","Fr","Sa","Su"]])

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=f"calday_{year:04d}-{month:02d}-{day:02d}"))
        markup.append(row)

    prev_m, prev_y = (month - 1, year) if month > 1 else (12, year - 1)
    next_m, next_y = (month + 1, year) if month < 12 else (1, year + 1)
    markup.append([
        InlineKeyboardButton("⬅️", callback_data=f"calnav_{prev_y:04d}-{prev_m:02d}"),
        InlineKeyboardButton("➡️", callback_data=f"calnav_{next_y:04d}-{next_m:02d}"),
    ])
    return InlineKeyboardMarkup(markup)

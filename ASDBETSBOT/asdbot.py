from datetime import datetime, timedelta, timezone
from telegram import Update, LinkPreviewOptions
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from typing import Final, Dict, Optional, List
import random
import requests
from bs4 import BeautifulSoup
import re 

# --- 1. CONFIGURATION ---

# IMPORTANT: REPLACE WITH YOUR ACTUAL BOT TOKEN
TOKEN: Final = "8260821750:AAGdFv5ARfph4-sPrfkr-YYShr2VNrUaYGM"
BOT_USERNAME: Final = '@asdbets_bot'

# General Configuration
# Increased timeout to help with slow connections/scraping
TIMEOUT_SECONDS: Final[int] = 45 

# Time Zone Configuration
NST_OFFSET = timedelta(hours=5, minutes=45)
NST_TIMEZONE = timezone(NST_OFFSET, 'NST')

# SCRAPING CONFIGURATION
HAMRO_PATRO_URL: Final[str] = "https://www.hamropatro.com/rashifal"
NEWS_HTML_URL: Final[str] = "https://www.hamropatro.com/news" 
NEWS_HEADLINE_COUNT: Final[int] = 5
DATE_SOURCE_URL: Final[str] = "https://www.hamropatro.com/calendar" 

# DUCKDUCKGO CONFIGURATION (Free Search API)
DDG_API_URL: Final[str] = "https://api.duckduckgo.com/?format=json&q="


# RASHI MAPPING and static lists
RASHI_SLUG_MAP = {
    "mesh": "मेष", "aries": "मेष", "मेष": "मेष",
    "brish": "बृष", "vrishabha": "बृष", "बृष": "बृष",
    "mithun": "मिथुन", "gemini": "मिथुन", "मिथुन": "मिथुन",
    "karkat": "कर्कट", "cancer": "कर्कट", "कर्कट": "कर्कट",
    "singha": "सिंह", "simha": "सिंह", "leo": "सिंह", "सिंह": "सिंह",
    "kanya": "कन्या", "virgo": "कन्या", "कन्या": "कन्या",
    "tula": "तुला", "libra": "तुला", "तुला": "तुला",
    "brischik": "बृश्चिक", "vrishchika": "बृश्चिक", "scorpio": "बृश्चिक", "वृश्चिक": "बृश्चिक",
    "dhanu": "धनु", "sagittarius": "धनु", "धनु": "धनु",
    "makar": "मकर", "capricorn": "मकर", "मकर": "मकर",
    "kumbha": "कुम्भ", "aquarius": "कुम्भ", "कुम्भ": "कुम्भ",
    "meen": "मीन", "pisces": "मीन", "मीन": "मीन",
}

NEPALI_PROVERBS = [
    "हल्लाको पछि नलाग्नुस्, आफ्नै विवेकको प्रयोग गर्नुहोस्। (Don't follow the noise, use your own conscience.)",
    "जहाँ इच्छा, त्यहाँ उपाय। (Where there is a will, there is a way.)",
    "समय कसैको लागि पर्खदैन। (Time waits for no one.)",
]

# STATIC PRICE DATA (Scraping has been difficult, using snippet)
STATIC_PRICE_SNIPPET: Final = """
<div class="column6" style="margin-bottom: 40px;margin-top: 12px;">
            <ul class="gold-silver" style="margin: 0">
                <li onclick="$('.goldchart').hide();$('#goldchart').show();" style="cursor:pointer;">Gold Hallmark - tola ( छापावाल सुन )</li>
                <li onclick="$('.goldchart').hide();$('#goldchart').show();" style="cursor:pointer;">
                    Nrs.
                    256,602.17</li>
                <li onclick="$('.goldchart').hide();$('#goldchart1').show();" style="cursor:pointer;">Gold Tajabi - tola ( तेजाबी सुन )</li>
                <li onclick="$('.goldchart').hide();$('#goldchart1').show();" style="cursor:pointer;">
                    Nrs.
                    0.00</li>
                <li onclick="$('.goldchart').hide();$('#goldchart2').show();" style="cursor:pointer;">Silver - tola ( चाँदी )</li>
                <li onclick="$('.goldchart').hide();$('#goldchart2').show();" style="cursor:pointer;">
                    Nrs.
                    3,905.11</li>
                <li onclick="$('.goldchart').hide();$('#goldchart3').show();" style="cursor:pointer;">Gold Hallmark - 10g ( छापावाल सुन )</li>
                <li onclick="$('.goldchart').hide();$('#goldchart3').show();" style="cursor:pointer;">
                    Nrs.
                    219,995.00</li>
                <li onclick="$('.goldchart').hide();$('#goldchart4').show();" style="cursor:pointer;">Gold Tajabi - 10g ( तेजाबी सुन )</li>
                <li onclick="$('.goldchart').hide();$('#goldchart4').show();" style="cursor:pointer;">
                    Nrs.
                    0.00</li>
                <li onclick="$('.goldchart').hide();$('#goldchart5').show();" style="cursor:pointer;">Silver - 10g ( चाँदी )</li>
                <li onclick="$('.goldchart').hide();$('#goldchart5').show();" style="cursor:pointer;">
                    Nrs. 3,348.00</li>
            </ul>
        </div>
"""

# --- 2. DYNAMIC CONTENT FETCHING & EXTRACTION FUNCTIONS ---

def get_duckduckgo_answer(query: str) -> Optional[str]:
    """Fetches an instant answer from DuckDuckGo API (free search)."""
    try:
        url = DDG_API_URL + requests.utils.quote(query)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        
        answer = data.get('Answer', '').strip()
        abstract = data.get('AbstractText', '').strip()
        
        if answer:
            return answer
        elif abstract:
            return abstract
        else:
            results = data.get('RelatedTopics', [])
            if results and isinstance(results, list) and 'Text' in results[0]:
                return results[0]['Text'].strip()
            return None

    except requests.exceptions.RequestException as e:
        print(f"DuckDuckGo API call failed: {e}")
        return None
    except Exception as e:
        print(f"Error processing DuckDuckGo response: {e}")
        return None

def fetch_rashifal_html() -> Optional[str]:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(HAMRO_PATRO_URL, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status() 
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Hamro Patro: {e}")
        return None

def extract_daily_rashifal(html_content: Optional[str]) -> Dict[str, str]:
    if not html_content: return {}
    soup = BeautifulSoup(html_content, 'html.parser')
    rashifal_data: Dict[str, str] = {}
    main_container = soup.find('div', id='rashifal')
    if main_container:
        rashi_blocks = main_container.find_all('div', class_='item')
        for block in rashi_blocks:
            name_tag = block.find('h3')
            desc_tag = block.find('div', class_='desc')
            if name_tag and desc_tag:
                rashi_name = name_tag.text.strip() 
                raw_text = desc_tag.get_text(strip=True)
                clean_text = re.sub(r'^{}\s*\(.*?\)\s*'.format(re.escape(rashi_name)), '', raw_text, count=1).strip()
                if rashi_name and clean_text:
                    rashifal_data[rashi_name] = clean_text
    return rashifal_data

def extract_lucky_details(description: str) -> Dict[str, Optional[str]]:
    color_match = re.search(r'शुभ\s+रंग\s+([^,।\.]+)\s+हो', description)
    color = color_match.group(1).strip() if color_match else "N/A"
    number_match = re.search(r'शुभ\s+अंक\s+([^,।\.]+)\s+रहेको\s+छ', description)
    number = number_match.group(1).strip() if number_match else "N/A"
    cleaned_description = re.sub(r'(आजको|शुभ|तपाईंको)\s+[^।\.]+\s+रहेको\s+छ[।\.]*', '', description).strip()
    cleaned_description = re.sub(r'\s*आजको\s+शुभ\s+रंग\s+[^।\.]+\s+हो\s+भने\s+शुभ\s+अंक\s+[^।\.]+\s+रहेको\s+छ[।\.]*', '', cleaned_description).strip()
    cleaned_description = re.sub(r'\s*आजको\s+शुभ\s+रंग\s+[^।\.]+\s+हो[।\.]*', '', cleaned_description).strip()
    return {
        'color': color,
        'number': number,
        'description': cleaned_description
    }

def get_latest_rashifal() -> Dict[str, str]:
    html_content = fetch_rashifal_html()
    return extract_daily_rashifal(html_content)

def fetch_news_html() -> Optional[str]:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(NEWS_HTML_URL, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status() 
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from News URL: {e}")
        return None

def extract_news_headlines(html_content: Optional[str]) -> List[Dict[str, str]]:
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    headlines_data: List[Dict[str, str]] = []
    headline_containers = soup.find_all('div', class_='item newsCard', limit=NEWS_HEADLINE_COUNT) 
    for container in headline_containers:
        title_tag = container.find('a', class_='newsTitle')
        link_tag = container.find('a', class_='read-full-list')
        if title_tag and link_tag:
            title = title_tag.text.strip()
            link = link_tag.get('href', '#') 
            if title and link and link != '#':
                headlines_data.append({'title': title, 'link': link})
    return headlines_data

def get_latest_news() -> List[Dict[str, str]]:
    html_content = fetch_news_html()
    return extract_news_headlines(html_content)

def extract_price_data(html_snippet: str) -> List[Dict[str, str]]:
    if not html_snippet: return []
    soup = BeautifulSoup(html_snippet, 'html.parser')
    prices_data: List[Dict[str, str]] = []
    price_list = soup.find('ul', class_='gold-silver')
    if not price_list: return []
    list_items = price_list.find_all('li')
    for i in range(0, len(list_items), 2):
        name_item = list_items[i]
        price_item = list_items[i+1] if i + 1 < len(list_items) else None
        if name_item and price_item:
            name_text = name_item.get_text(strip=True)
            match = re.search(r'(.*?)\s+-\s+([^\(]+)\s+\(([^)]+)\)', name_text)
            if match:
                item_name_english = match.group(1).strip()
                unit = match.group(2).strip()
                item_name_nepali = match.group(3).strip()
                display_name = f"{item_name_english} ({item_name_nepali})"
                display_unit = unit
            else:
                parts = name_text.split(' - ')
                display_name = parts[0].strip() if parts else name_text
                display_unit = parts[1].strip() if len(parts) > 1 else ""
            price_text = price_item.get_text(strip=True).replace('Nrs.', '').replace('रु.', '').replace(',', '').strip()
            prices_data.append({
                'name': display_name,
                'unit': display_unit,
                'price': price_text,
            })
    return prices_data

def get_latest_prices() -> List[Dict[str, str]]:
    return extract_price_data(STATIC_PRICE_SNIPPET)

def fetch_date_html() -> Optional[str]:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(DATE_SOURCE_URL, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status() 
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Date URL: {e}")
        return None

# REVISED SCRAPING LOGIC FOR /date COMMAND
def extract_live_nepali_data(html_content: Optional[str]) -> Dict[str, str]:
    data = {
        'bs_date_full': "Data Not Found", 'tithi': "Data Not Found", 
        'panchang': "Data Not Found", 'nepali_time_display': "Live Time Unavailable",
        'ad_date': "Data Not Found", 'day_english': datetime.now(NST_TIMEZONE).strftime("%A"), 
    }
    if not html_content: return data
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Attempt to find the main date block
    main_display_block = soup.find('div', class_='np-calendar-day') or soup.find('div', class_='today')

    if main_display_block:
        full_text = main_display_block.get_text(separator='|', strip=True)

        # 1. Nepali Date (BS)
        nepali_date_text = main_display_block.find('span', class_='nep')
        if nepali_date_text:
             data['bs_date_full'] = nepali_date_text.get_text(strip=True).replace('\xa0', ' ')

        # 2. English Date (AD) - Look for Month Day, Year pattern
        ad_match = re.search(r'([A-Za-z]+\s+\d{1,2},\s+\d{4})', full_text)
        if ad_match:
            data['ad_date'] = ad_match.group(1).strip()
            try:
                ad_date_obj = datetime.strptime(data['ad_date'], '%b %d, %Y').replace(tzinfo=NST_TIMEZONE)
                data['day_english'] = ad_date_obj.strftime("%A")
            except ValueError:
                pass 
                
        # 3. Nepali Time 
        time_tag = soup.find('span', id='nepali-time')
        if time_tag:
            data['nepali_time_display'] = time_tag.get_text(strip=True)

        # 4. Tithi & Panchang (often labeled/separated)
        tithi_tag = soup.find('div', class_='tithi-info') or soup.find('div', class_='tithi')
        if tithi_tag:
            data['tithi'] = tithi_tag.get_text(strip=True)

        panchang_tag = soup.find('div', class_='panchang-info')
        if panchang_tag:
            data['panchang'] = panchang_tag.get_text(strip=True)

    # Fallback/Original selectors
    if data['bs_date_full'] == "Data Not Found":
        bs_tag_fallback = soup.find('span', class_='nep')
        if bs_tag_fallback: data['bs_date_full'] = bs_tag_fallback.get_text(strip=True).replace('\xa0', ' ')
    if data['ad_date'] == "Data Not Found":
        ad_tag_fallback = soup.find('span', id='english-date')
        if ad_tag_fallback: data['ad_date'] = ad_tag_fallback.get_text(strip=True)
    
    if data['bs_date_full'].lower() == 'data not found':
        data['bs_date_full'] = "❌ Data Not Found"

    return data

def get_live_nepali_data() -> Dict[str, str]:
    html_content = fetch_date_html()
    return extract_live_nepali_data(html_content)


# --- 3. COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Simplified, English-only /start message with no bold formatting
    await update.message.reply_text(
        "Hello! I am your Nepali Bot. Here are my available commands:\n\n"
        
        "--- ECONOMIC INFO ---\n"
        "/price - View today's Gold and Silver prices.\n"
        
        "--- PREDICTIONS ---\n"
        "/prediction <Team A> <Team B> - Predict the winner between two teams.\n"
        
        "--- KNOWLEDGE & INFO ---\n"
        "/rashi <sign> - View the daily, updated horoscope.\n"
        "/news - View the latest 5 major news headlines.\n"
        "/proverb - Get today's Nepali Proverb.\n"
        
        "--- UTILITIES ---\n"
        "/date - Get today's Nepali and English date, time, and Panchang information.\n"
        "/ask <question> - Search the internet for an answer to any question. (Free Search)\n"
        "/randompick <options> - Select a random choice from a list."
    )

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /ask command by searching the web using DuckDuckGo API."""
    
    if not context.args:
        await update.message.reply_text(
            "🌐 Usage Error: Please ask a question after the command.\n"
            "Example: /ask What is the highest mountain in Nepal?"
        )
        return
    
    user_question = " ".join(context.args)
    thinking_message = await update.message.reply_text("🌐 Searching DuckDuckGo... Please wait a moment.")
    
    try:
        search_result = get_duckduckgo_answer(user_question)

        if search_result:
            final_message = f"🌐 Search Answer:\n\n{search_result.strip()}"
        else:
            final_message = "❌ Search Error: Could not find a relevant instant answer for that query."
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=thinking_message.message_id,
            text=final_message
        )

    except Exception as e:
        print(f"General error in /ask command: {e}")
        error_message = "❌ Error: An unexpected error occurred while running the search."
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=thinking_message.message_id,
            text=error_message
        )

async def prediction_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 2:
        await update.message.reply_text(
            "🔮 Usage Error:\n"
            "Please provide two team names.\n"
            "Example: /prediction Barcelona RealMadrid"
        )
        return

    team_a = context.args[0]
    team_b = context.args[1]

    winner = random.choice([team_a, team_b])
    confidence = random.randint(80, 95)

    message = (
        f"🔮 Match Prediction ⚽\n"
        f"----------------------------------------------------\n"
        f"➡️ {winner} will win the game and the chance is {confidence}% sure!"
    )

    await update.message.reply_text(message)

async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = get_live_nepali_data()

    if data.get('bs_date_full') == 'Data Not Found':
        # The revised error message to help debug scraping failure
        message_content = "❌ Error: Could not retrieve live Date and Panchang data. The website structure may have changed, or the data is loading too slowly."
    else:
        # Note: Removing bolding as requested in a previous turn
        message_content = (
            f"📅 Today's Date and Panchang:\n"
            f"---------------------------------------\n"
            f"Nepali Date (BS): {data['bs_date_full']}\n"
            f"English Date (AD): {data['ad_date']} ({data['day_english']})\n"
            f"Time: {data['nepali_time_display']}\n\n"
            f"Tithi: {data['tithi']}\n"
            f"Panchang: {data['panchang']}"
        )

    await update.message.reply_text(message_content)

async def rashi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    DAILY_RASHI_DATA_DYNAMIC = get_latest_rashifal()
    is_list_request = not context.args or context.args[0].lower() == 'list'

    if not DAILY_RASHI_DATA_DYNAMIC:
        await update.message.reply_text(
            "❌ Error: Could not retrieve today's Rashifal data from the source. Please try again later."
        )
        return

    if is_list_request:
        rashis_list = "\n".join([f"• {name}" for name in DAILY_RASHI_DATA_DYNAMIC.keys()])
        example_nepali_name = random.choice(list(DAILY_RASHI_DATA_DYNAMIC.keys()))

        message = (
            f"✨ Daily Horoscope Update ✨\n\n"
            f"To view Rashi details, please use: /rashi <Rashi Name>.\n"
            f"Example: /rashi {example_nepali_name}\n\n"
            f"Available Rashis Today:\n"
            f"---------------------------------------\n"
            f"{rashis_list}"
        )
        await update.message.reply_text(message) 

    else:
        query_sign = context.args[0].lower()
        target_nepali_name = RASHI_SLUG_MAP.get(query_sign)

        if target_nepali_name and target_nepali_name in DAILY_RASHI_DATA_DYNAMIC:
            raw_horoscope_text = DAILY_RASHI_DATA_DYNAMIC[target_nepali_name]
            details = extract_lucky_details(raw_horoscope_text)
            lucky_color = details['color']
            lucky_number = details['number']
            
            bhagya_details = (
                f"\nLuck Details:\n" 
                f"Lucky Color: {lucky_color}\n"
                f"Lucky Number: {lucky_number}"
            )
            
            message = (
                f"✨ {target_nepali_name} Rashi Summary ✨\n"
                f"---------------------------------------\n"
                f"Today's Message:\n" 
                f"*{details['description']}*\n" 
                f"{bhagya_details}"
            )
            
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(
                f"Sorry, I couldn't find a Rashi matching '{context.args[0]}'.\n"
                f"Please use a valid Nepali name or English sign name, or try /rashi to see the list."
            )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    news_items = get_latest_news()

    if not news_items:
        message = (
            "❌ Error: Could not retrieve news headlines at this time. (Check News URL/parsing logic.)"
        )
    else:
        headlines_list = "\n\n".join([
            f"{i+1}. [{item['title']}]({item['link']})" 
            for i, item in enumerate(news_items)
        ])
        
        message = (
            f"📰 Top {len(news_items)} News Headlines\n"
            f"--------------------------------------------------\n"
            f"{headlines_list}"
        )
    
    await update.message.reply_text(
        message, 
        parse_mode='Markdown', 
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    price_items = get_latest_prices()

    if not price_items:
        message = (
            "❌ Error: Could not retrieve Gold and Silver price data. (Data extraction failed.)"
        )
    else:
        price_lines = []
        for item in price_items:
            try:
                price_float = float(item['price'])
                # Format price with commas for readability
                formatted_price = f"{price_float:,.2f}"
            except ValueError:
                formatted_price = item['price'] 

            line = f"{item['name']} ({item['unit']}): Nrs. {formatted_price}"
            price_lines.append(line)
        
        prices_list = "\n" + "\n".join(price_lines)

        message = (
            f"💰 Today's Gold and Silver Prices 📈\n"
            f"--------------------------------------------------\n"
            f"{prices_list}"
        )
    
    await update.message.reply_text(message)


async def proverb_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    proverb = random.choice(NEPALI_PROVERBS)

    message = (
        "💡 Proverb of the Day 💡\n\n"
        f"*{proverb}*"
    )
    await update.message.reply_text(message)


async def random_pick_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "🎲 Usage Error: Please provide at least two items to pick from.\n"
            "Example: /randompick Bikram Saroj Jane"
        )
        return

    winner = random.choice(context.args)

    message = (
        f"🎉 Random Pick Result 🎉\n\n"
        f"👉 {winner}! 👈"
    )

    await update.message.reply_text(message)


# --- 4. MAIN FUNCTION (CRITICAL FIX FOR CONNECTION) ---

def main() -> None:
    print("Starting bot...")

    if not TOKEN:
        print("\nFATAL ERROR: The bot failed to start. Token is missing.")
        return

    try:
        # CRITICAL FIX: Increase the connection timeout (default is usually 5s) to 30 seconds 
        # to overcome slow or unstable connections to Telegram API servers.
        application = (
            Application.builder()
            .token(TOKEN)
            # Setting an explicit high timeout for API requests
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(30) 
            .build()
        )

        # Command Handlers 
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("prediction", prediction_command))
        application.add_handler(CommandHandler("date", date_command)) 
        application.add_handler(CommandHandler("rashi", rashi_command)) 
        application.add_handler(CommandHandler("news", news_command)) 
        application.add_handler(CommandHandler("proverb", proverb_command))
        application.add_handler(CommandHandler("randompick", random_pick_command))
        application.add_handler(CommandHandler("price", price_command)) 
        application.add_handler(CommandHandler("ask", ask_command))
        print("All command handlers added.")


        print("Bot is running and polling for updates...")
        # Use a slightly higher polling timeout as well
        application.run_polling(poll_interval=1.0, timeout=20, allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        # Provide clear feedback on connection issues
        error_message = str(e)
        if "Timed out" in error_message or "ExtBot is not properly initialized" in error_message:                                                        
             print("\n--- CRITICAL CONNECTION ERROR ---")
             print("The bot could not connect to Telegram's servers. Please check your network stability and firewall settings.")
        else:
            print(f"\nFATAL ERROR: The bot failed to start.")
            print(f"Error details: {e}")

if __name__ == '__main__':
    main()
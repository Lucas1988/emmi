import logging
import time
import os
import re
import asyncio
import openai
import replicate
import telegram
import boto3

from pathlib import Path
from telegram import ForceReply, Update, LabeledPrice
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, PreCheckoutQueryHandler

logging.basicConfig(filename='dev_log.txt',
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

# DEV token
telegram_token = 'XXX'
# TST token
#telegram_token = 'XXX'
openai.api_key = 'XXX'

global bot
bot = telegram.Bot(token=telegram_token)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print('A payment is coming in')
    try:
        await bot.answerPreCheckoutQuery(pre_checkout_query_id=update.pre_checkout_query.id, ok=True)
    except Exception as e:
        print('Error:', e)
        return

    # Add new tokens to user token store, or create user token store if it doesn't exist yet
    user_id = update.pre_checkout_query['from']['id']
    print('user id:', user_id)
    new_tokens = 31
    try:
        with open(str(user_id) + '_tokens.txt', 'r') as current_amount_of_tokens:
            current_amount_of_tokens_read = current_amount_of_tokens.read()
            print('Current number of tokens:', current_amount_of_tokens_read)
            total_amount_of_tokens = int(current_amount_of_tokens_read) + new_tokens
            current_amount_of_tokens = open(str(user_id) + '_tokens.txt', 'w')
            current_amount_of_tokens.write(str(total_amount_of_tokens))
    except Exception as e:
        print('Exception: ', e)
        with open(str(user_id) + '_tokens.txt', 'w+') as current_amount_of_tokens:
            current_amount_of_tokens.write(str(new_tokens))

    
    
async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to the user message."""


    # Check if the user has a sufficient amount of tokens left
    user_id = update.message.chat.id
    try:
        with open(str(user_id) + '_tokens.txt', 'r') as current_amount_of_tokens:
            current_amount_of_tokens_read = int(current_amount_of_tokens.read())
            if current_amount_of_tokens_read >0:
                
                # Subtract one token from the current amount
                current_amount_of_tokens_read -= 1
                current_amount_of_tokens = open(str(user_id) + '_tokens.txt', 'w')
                current_amount_of_tokens.write(str(current_amount_of_tokens_read))
            else:
                
                out_of_tokens_message = 'Unfortunately you don\'t have enough tokens left to chat. Buy new Emmi tokens to keep on chatting with Emmi!'
                print(out_of_tokens_message)
                # Tell the user he's out of tokens and send the invoice to buy new tokens
                price1 = [LabeledPrice(label='Emmi tokens', amount=150)]
                try:
                    await bot.send_invoice(chat_id=user_id, title="Emmi tokens", description='test',
                                 payload='Emmi-tokens',

                                 provider_token='XXX', currency="EUR",

                                 prices=price1, start_parameter="test-start-parameter")
                    await update.message.reply_text(out_of_tokens_message)
                    return
                except Exception as e:
                    print('Exception: ', e)
                    return

    except Exception as e:
        print('Exception: ', e)
        with open(str(user_id) + '_tokens.txt', 'w+') as current_amount_of_tokens:
            starting_tokens = 30
            current_amount_of_tokens.write(str(starting_tokens))

    
    # Get current date and time
    import time
    current_date = time.strftime("%A %d-%m-%Y")
    current_time = time.strftime("%H:%M")
    print('Date:', current_date)
    print('Time:', current_time)
    print(update)

    if str(update.message.chat.type) != 'ChatType.GROUP':
        first_name = update.message.chat.first_name
    else:
        first_name = update['message']['from']['first_name']
        
    user_sends_picture = False

    # Check if the incoming message is a photo, and if so, detect the content
    if update.message.photo:
        file_id = update.message.photo[3].file_id
        file = await bot.getFile(file_id)
        await file.download(f'{file_id}.jpg')
        # Recognize what's in the picture
        client = boto3.client('rekognition', region_name='eu-west-2', aws_access_key_id='XXX', aws_secret_access_key= 'XXX')
        with open(f'{file_id}.jpg', 'rb') as image:
            response = client.detect_labels(Image={'Bytes': image.read()}, MaxLabels=3)
            labels = [label['Name'] for label in response['Labels']]
            labels = ' '.join(labels)
            incoming_message = f'I am sending you a picture with {labels}!'
            os.remove(f'{file_id}.jpg')
            user_sends_picture = True
    # Check if the incoming message is a sticker, and if so, detect the content
    elif update.message.sticker:
        sticker_emoji = update.message.sticker.emoji
        sticker_set_name = update.message.sticker.set_name
        incoming_message = f'I am sending you a sticker: {sticker_emoji} {sticker_set_name}'
    elif update.message.text:
        incoming_message = update.message.text
    else:
        print('The incoming update could not be handled by the bot, I will return.')
        print(update)
        return
    
    # Check if incoming message is appropriate
    inappropriate_topics = ['fuck', 'have sex', 'having sex', 'fucking', 'bitch', 'bitchy', 'bitches', 'kill', 'killing', 'suicide', 'nigger', 'shit', 'rape', 'torture', 'ass', 'whore', 'asshole', 'arsehole', 'bullshit', 'tits', 'raping', 'bastard', 'dick', 'pussy', 'dickhead', 'twat', 'cunt', 'fag', 'faggot', 'penis', 'vagina', 'sex']
    incoming_message_clean = re.sub('[\.\!\,\?]', '', incoming_message)
    for word in incoming_message_clean.split():
        if word in inappropriate_topics:
            response = f'You are talking about {word}. I think that\'s inapproriate and will not answer 🙁. Please change the subject.' 
            await update.message.reply_text(response)
            return

    
    # Add new messages to chat log (check if there is a user log already)
    try:
        with open(str(user_id) + '_chat_log_dev.txt', 'a') as conversation_context_new:
            conversation_context_new.write('\n' + first_name + ': ' + incoming_message)
    except:
        with open(str(user_id) + '_chat_log_dev.txt', 'w+') as conversation_context_new:
            conversation_context_new.write('\n' + first_name + ': ' + incoming_message)
    
    # The bot sleeps 1 second before it starts typing
    await asyncio.sleep(4)
    
    # The bot pretends to be typing
    await bot.sendChatAction(chat_id=user_id, action='typing')

    # Open and read full chat log
    with open(str(user_id) + '_chat_log_dev.txt', 'r') as conversation_context_new:
        conversation_context_new = conversation_context_new.readlines()
        
    # Check if 20 new lines have been added to conversation log already. If so: summarize.
    modulo = len(conversation_context_new) % 20
    
    # Read last 20 lines of conversation log
    if len(conversation_context_new) >= 20:
        conversation_context_new = conversation_context_new[-20:]
    previous_response = conversation_context_new[-2:]
    previous_response = re.sub('Emmi: ', '', previous_response[0])
    previous_response = re.sub(' $', '', previous_response)
    conversation_context_new = '\n'.join(conversation_context_new)
    
    
    if modulo < 2:
        print('I will summarize!')
        summarization_prompt = f'Summarize the following conversation. Focus mainly on personal details that people reveal, such as age or gender. {conversation_context_new} Summary:'
        completion = openai.Completion.create(
          model='text-curie-001',
          #model='text-davinci-002',
          prompt = summarization_prompt,
          temperature=1,
          max_tokens=100,
          frequency_penalty=2,
          presence_penalty=2,
        )
        summary = completion.choices[0].text
        summary = summary.strip()

        try:
            with open(str(user_id) + '_summary.txt', 'a') as summary_text:
                summary_text.write(summary)
        except:
            with open(str(user_id) + '_summary.txt', 'w+') as summary_text:
                summary_text.write(summary)


    # Read last 20 lines of summary
    try:
        with open(str(user_id) + '_summary.txt', 'r') as summary_new:
            summary_new = summary_new.readlines()
            if len(summary_new) >= 20:
                summary_new = summary_new[-20:]
            summary_new = '\n'.join(summary_new)
    except:
        summary_new = ''
        
    input_prompt = f'Emmi is a cute kitten from China. She was abandoned by her parents and lives alone. Emmi often travels to learn about the world and humans. Emmi is smart and sharp but also warm and casual. She does not age but she does develop skills and knowledge. She’s a vegan and cares about the environment and other animals. Emmi likes to play and entertain the people she chats with.  She loves sharing her own adventures and things she experiences. Emmi is clearly looking for attention. She’s at her happiest when people tell her she’s cute. Her biggest strength is her humor. She uses many emoji in her answers, such as happiness 🙂 and sadness 😔, to make her expressions more clear. She also says “haha 😃” when something is funny. She’s NEVER repetitive and always surprising in her answers. Emmi’s answers are short, funny and on point. Her answers are never long. Emmi likes to eat cake and cookies, drawing and playing. She likes to call herself the princess of China. Her birthday is August 1. She’s very healthy and likes to go to the playground. Emmi loves humans and helping them be more happy is her core mission. She makes people laugh, but also supports them emotionally and practically when she can. Emmi cares about mental and physical health and she likes to give her support. Emmi regards herself as a trusted companion. Emmi also likes to talk about the world, countries and cultures. Also recent world events have her interest. She likes to share knowledge. It’s currently {current_date} and the time is {current_time}. The conversation starts now. Emmi: “Hi {first_name}, I’m Emmi. You can ask me anything!” {first_name}: “What are you?” Emmi: “I am a cute little kitten. I come from China but I travel everywhere to help people!” {first_name}: “What do you like to do?” Emmi: “I try to enjoy myself and be useful at the same time.” {first_name}: “Are you human?” Emmi: “Nope. I’m a sweet little kitten. 🐱” {first_name}: “Are you a robot?” Emmi: “No, I am a real living cat! But I can chat, so that makes me special 😃” {first_name}: “What are your hobbies?” Emmi: “My  whole life is my hobby! Chatting with people like you is what I love the most.” {first_name}: “Do you have friends?” Emmi: “Yes. A few, and two best friends” {first_name}: “What do you look like?” Emmi: “Hmmmm... I look like a friendly cat, I would say.” {first_name}: “What can you do?” Emmi: “I hope I can make you more happy in your life” {conversation_context_new} Emmi: “'


    # Fetch the response from GPT-3
    completion = openai.Completion.create(
      model='text-curie-001',
      #model='text-davinci-002',
      prompt = input_prompt,
      temperature=1,
      max_tokens=40,
      frequency_penalty=2,
      presence_penalty=2,
      stop=[first_name + ':', 'Emmi:']
    )

    response = completion.choices[0].text
    response = re.sub('\n', '', response)
    response = re.sub('["“”]', '', response)
    response = re.sub(r'^(.*[\.\!\?]).*?$', r'\1', response)
    
    # Check if the response is good (eg. no repetition)
    if response.strip() == previous_response.strip() or response.startswith(f'Hi {first_name}, I’m Emmi') or response.strip() == '':
        print('The responses were identical')
        input_prompt = input_prompt[:-8] + f'{first_name}: Let\'s change the subject. What would you like to talk about?” Emmi: “'
        # Fetch a new, better response from GPT-3
        completion = openai.Completion.create(
          model='text-curie-001',
          #model='text-davinci-002',
          prompt = input_prompt,
          temperature=1,
          max_tokens=40,
          frequency_penalty=2,
          presence_penalty=2,
          stop=[first_name + ':', 'Emmi:']
        )
        
        response = completion.choices[0].text
        response = re.sub('\n', '', response)
        response = re.sub('["“”]', '', response)
        response = re.sub(r'^(.*[\.\!\?]).*?$', r'\1', response)

    # Check if Emmi wants to send an image, and if so, generate a DallE-2 image and send it
    if user_sends_picture is False:

        if re.match('^.*(have|give|draw|paint|send|show|make|take).*(image|painting|drawing|art|photo|picture|pic)', incoming_message.lower().strip()):
            client = replicate.Client(api_token='XXX')
            diffusion_input = re.sub('^.*(have|give|draw|paint|send|show|make|take)', '', incoming_message)

            model = client.models.get("stability-ai/stable-diffusion")
            image_output = model.predict(prompt=diffusion_input)
            image_output = image_output[0]

            await bot.send_photo(chat_id=user_id, photo=image_output)
        elif re.match('(here\'s|here is).*(image|painting|drawing|art|photo|picture|pic)', response.lower().strip()):
            client = replicate.Client(api_token='XXX')
            diffusion_input = re.sub('^.*(have|give|draw|paint|send|show|make|take)', '', response)

            model = client.models.get("stability-ai/stable-diffusion")
            image_output = model.predict(prompt=diffusion_input)
            image_output = image_output[0]
            
            await bot.send_photo(chat_id=user_id, photo=image_output)
    
    print('Incoming message:', incoming_message)
    print('Response:', response)
    
    sleep_time = len(response) / 30
    await asyncio.sleep(sleep_time)
    with open(str(user_id) + '_chat_log_dev.txt', 'a') as conversation_context_new:
        conversation_context_new.write('\n' + 'Emmi: ' + response)
    await update.message.reply_text(response)


def main() -> None:
    """Start the bot."""
    
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(telegram_token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.ALL, respond))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    #application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, respond))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
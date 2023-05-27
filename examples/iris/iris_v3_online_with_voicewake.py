"""IRIS - Intelligent Residential Interface System
This version uses google for STT and TTS, and OpenAI for inference, and so it works REALLY well but is not private.
Note that it's using text-davinci-002 (GPT3) - if you have GPT-4 API access you will need to change the script.
I might do that if/when I eventually get GPT-4 access.

Here we replace the 'push to talk' button with a wake word.  Iris is asleep when it starts up and you need to say
"Pay attention Iris" for it to start listening properly.  Once Iris is awake, you can simply say "Iris" in order to
speak.  There's a chirp to let you know that it's understood your wake word.  You can say "Stop paying attention" to
make it stop paying attention.  While it's waiting for a wake word, it does not send your audio to the internet.  Once
it's awake and listening (after your "Iris" wake word), then your audio is sent to online services for processing.
We'll use wav2vec2 for the offline STT step (while listening for the wakeword).

One of the problems with the wakeword system is that it might be interpreting some long sentence it's hear while you're
trying to say the wakeword, and you just have to wait silently until it's ready.  It can be tricky to know when it's
ready, which is why it outputs ':' and '.' during the "waiting for wakeword" phase.  ':' means it's ready to listen.  If
you see a '.', that means it's picked up some audio and you'll have to wait for the next ':' before you can say the
wakeword.  I tried using audio prompts for this, but it was too annoying.  This is one of the reasons I prefer to use
a push-to-talk (really a mute mic) button on my bluetooth speaker in later versions of Iris.

Put your OpenAI API key in your environment variables as OPEN_AI_API_KEY
BE CAREFUL NOT TO SHARE YOUR OPENAI API KEY!
This version adds a few chirps and bleeps which makes it easier to know what's going on if you aren't looking at
the screen.  It seems a little thing, but it makes a lot of difference later when we're not even near our computer!
"""
# Clear the terminal
print("\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n")
print("\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n")
print("Iris: Loading, please wait...")

from pydub import AudioSegment
from pydub.playback import play

# load sound effects - some of the other imports take a while to load, so we can start chirping now to show that we're
# busy loading everything in.  "loading.mp3" is a sample of our chosen voice saying "loading, please wait"
loading = AudioSegment.from_mp3('loading.mp3')
play(loading)

import numpy as np
import sounddevice as sd
# And now we can play a waiting noise while we load the rest - reason for using sound device is because it can play
# in the background while we continue to work.  Reason for using numpy is.. well it's how I got this to work... I think
# there are probably better ways :)
working = AudioSegment.from_mp3('workinglongquiet.mp3')
workinga = np.array(working.get_array_of_samples())
sd.play(workinga, working.frame_rate*2)

# Load some more sounds
chirp = AudioSegment.from_mp3('chirp.mp3')
bleep = AudioSegment.from_mp3('bleep.mp3')
longbleep = AudioSegment.from_mp3('longbleep.mp3')

# Now load all the other imports that can take a long time to load (not too long here but when we start using offline
# models the loading takes a while).  I guess the linter would prefer us to do all our imports at the top, but I like
# to get this feedback during startup.
from gtts import gTTS
from io import BytesIO
import speech_recognition as sr
import openai
from collections import deque
from wakeup.wakelistener import listen_for_wakeword
import os


# Speak the text out loud
def speak(text):
    sd.stop() # stop any busy sound we're playing
    tts = gTTS(text, lang='en', tld='com.au')
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    fromfp = AudioSegment.from_file(mp3_fp, format="mp3")
    play(fromfp)


# Return only when the user presses space (Windows specific library, sorry!)
def wait_for_space():
    c = 'a'
    while c != b' ':
        c = m.getch()
        time.sleep(0.1)
    while m.kbhit(): # waste any more input in the buffer before returning
        c= m.getch()


# Plays the 'I'm busy' bleep sequence indefinitely (until sd.stop() is called again)
def play_working_sound():
    sd.stop()
    sd.play(workinga, working.frame_rate*2, loop=True) # start playing working noise


# Wait for the user to press space, then grab a sample of their speech.  If they say "exit" exit the script, otherwise
# print the text and return it.
def listen_for_user_input(wait_for_wakeword):
    try:
        with sr.Microphone(sample_rate=16000) as source:
            # listen
            print(f"You: ", end='', flush=True)
            play(chirp) # "ready to listen" bleep

            # Wait until the user says the 'wakeword'
            if wait_for_wakeword:
                result = listen_for_wakeword()
                while not result:
                    result = listen_for_wakeword()

            play(bleep) # "listening" bleep
            print(f"(listening...) ", end='', flush=True)
            audio = r.listen(source)
            print(f"(heard...) ", end='', flush=True)
            play(chirp) # listening finished, parsing text about to start

            # parse and tokenize audio
            play_working_sound()
            text = r.recognize_google(audio)
            print(text)
            exit_if_exit(text)
            return text
    except Exception as e:
        sd.stop()
        print("Exception {0}".format(e))
        return None


# If text is "exit", exit the script
def exit_if_exit(text):
    if( text == 'exit'):
        print("Iris: Shutting down")
        speak("shutting down")
        exit()


# Make Iris say a friendly hello
def first_time_prompt():
    sd.stop()
    print("Iris: Nice to see you again, how can I help?")
    speak("Nice to see you again, how can I help?")


# Build the prompt for sending to the model, by zipping together all the human prompts and ai responses so far
def make_prompt():
    prompt = preamble
    for h, a in zip(human_prompts, ai_replies):
        prompt += restart_sequence + h + start_sequence + a
    return prompt


# Call GPT to get a response
def get_response(prompt):
    prompt += "\n'''"
    response = openai.Completion.create(
        model="text-davinci-002",
        prompt=prompt,
        temperature=0.9,
        max_tokens=512,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.6,
        stop=["'''"]
        )
    return response.choices[0].text.replace("\n", "").replace("AI:", "")


# Print and say the reply from the model
def output_ai_reply(reply):
    print("Iris: ", reply)
    speak(reply)


# This will be used repeatedly in a loop - listen for one user input, send to the model, say the response, append
# to the human_prompts and ai_replies queues
def interact_one_cycle():
    try:
        user_input = listen_for_user_input(True)
        while user_input is None:
            user_input = listen_for_user_input(False)
        prompt = make_prompt() + restart_sequence + user_input
        result = get_response(prompt)
        output_ai_reply(result)
        human_prompts.append(user_input)
        ai_replies.append(result)
    except Exception as e:
        print("Exception {0}".format(e))


# Main
if __name__ == "__main__":
    # Load the speech recognizer
    r = sr.Recognizer()

    # Grab the OpenAI API key from the user's environment
    openai.api_key = os.environ['OPENAI_API_KEY']

    # We have to keep track of our own conversation history -
    # we'll use length-limited queue for human prompts and ai replies.
    # A longer history_length will give the system more memory of previous interactions.
    history_length = 10
    human_prompts = deque(maxlen=history_length)
    ai_replies = deque(maxlen=history_length)

    # This is the preamble that will be used in every interaction
    preamble = "The following is a conversation with an AI assistant.  The assistant is helpful, creative, clever, \
               and very friendly."

    # And the prompts will be primed with these examples (which will scroll off as we reach history_length)
    human_prompts.append("Hello, how are you?")
    ai_replies.append("I am an AI created by OpenAI.  How can I help you today?")

    # These are the start and restart sequences.  We need them so that we can include them in our prompts, and strip these
    # from the responses when we print the output.
    start_sequence = "\nAI: "
    restart_sequence = "\nHuman: "

    # Say hello
    first_time_prompt()

    # And repeatedly listen and respond until the user chooses to exit
    while True:
        interact_one_cycle()

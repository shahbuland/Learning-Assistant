from typing import List, Iterable
from abc import abstractclassmethod
from copy import deepcopy
import os
import json
import re

from secret import API_KEY
import openai

openai.api_key = API_KEY

class BaseChatHarness:
    """
    Base class for all chat bots that make use of tools

    :param verbosity: 0 = no prints, 1 = print all model generated text, 2 = print all model generated text and tool calls
    """
    def __init__(self, init_prompt, debug_mode = False, init_messages : List[str] = [], engine = "gpt-3.5-turbo", verbosity = 0):
        if os.path.isfile(init_prompt):
            with open(init_prompt, 'r') as file:
                init_prompt = file.read()
        
        self.model = engine

        self.messages = [
            {"role":"system", "content":init_prompt}
        ]

        for i in range(0, len(init_messages), 2):
            self.messages.append({"role":"user", "content":init_messages[i]})
            if i+1 < len(init_messages):
                self.messages.append({"role":"assistant", "content":init_messages[i+1]})

        self.message_base = deepcopy(self.messages)
        self.debug_mode = debug_mode
        self.verbosity = verbosity

        self.message_decorators = {}

    def reset(self):
        self.messages = deepcopy(self.message_base)
    
    def update_decoration(self, key, val):
        self.message_decorators[key] = val

    def decorate_messages(self, msg_list : Iterable):
        msg_list = deepcopy(msg_list)
        for key in self.message_decorators:
            msg_list[0]['content'] += f"\n ==== {key} ====\n {self.message_decorators[key]}\n ========"

        return msg_list

    def __call__(self, msg : str):
        return self.converse(msg)
        
    def converse(self, user_input, mode = "user"):
        # Any outputs that are from a tool will get "TOOL RESULT:" added to start
        # This is to differentiate from actual user input

        if type(user_input) is not str:
            user_input = str(user_input)

        if mode == "tool":
            user_input = "TOOL RESULT: " + user_input
            if self.debug_mode:
                print("User: " + user_input)

        self.messages.append({"role":"user", "content":user_input})

        # If not in debug try and generate response from API
        # Otherwise get user input as a debug value
        try:
            if not self.debug_mode:
                response = openai.ChatCompletion.create(
                    model = self.model,
                    messages = self.decorate_messages(self.messages),
                    temperature = 0
                )
                reply =  response['choices'][0]['message']['content']
            else:
                reply = input("Assistant:")
        except Exception as e:
            del self.messages[-1]
            return f"API Error : {e}"

        self.messages.append({"role":"assistant", "content":reply})
        
        return self.sanitize_response(reply)

    @abstractclassmethod
    def sanitize_response(self, message : str):
        """
        Sanitize the final response to the user, i.e. to extract external dialogue or just generally to post proecess messages
        """
        return message

class ConceptExpanderChat(BaseChatHarness):
    def __init__(self, init_prompt = "LearnAssist/prompts/json_prompt.txt", engine = "gpt-3.5-turbo", **kwargs):
        super().__init__(init_prompt, engine = engine, **kwargs)
    
    def sanitize_response(self, message):
        try:
            json_start = message.find("```json")
            assert json_start != -1, "Couldn't find JSON block"
            json_end = message.find("```", json_start + len("```json"))
            s = message[json_start:json_end].strip()
        except:
            s = message
        data = json.loads(s)
    
        return data

    
from LearnAssist.chat_harness import ConceptExpanderChat

print("Format: [Concept], [Topic], [Scope], [Direction]")
chat = ConceptExpanderChat()
x = input()
print(chat.converse(x))
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model='gpt-4o')


def replay(messages: list[dict]) -> str:
    messages = [{"role": "system", "content": "You are a helpful assistant of Mijo."}] + messages
    lc_messages = []
    for msg in messages:
        if msg["role"] == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))
        elif msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))
    return llm(lc_messages).content


if __name__ == "__main__":
    msgs = [
        {"role": "user", "content": "What's the capital of France?"}
    ]
    response = replay(msgs)
    print(response)

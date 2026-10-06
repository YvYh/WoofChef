import spacy

class IngredientExtractor:
    def __init__(self):
        try:
            self.nlp = spacy.load("zh_core_web_sm")
        except Exception as e:
            print(f"NLP 模型加载失败，请确保在 Dockerfile 中执行了下载命令: {e}")
            self.nlp = None

    def extract(self, text, dynamic_whitelist=set(), dynamic_blacklist=set()):
        if not self.nlp or not text.strip(): return []
        doc = self.nlp(text)
        extracted = set()

        for token in doc:
            word = token.text

            # 黑名单优先：只要在黑名单里，绝对不提取
            if word in dynamic_blacklist:
                continue
            # 白名单其次：强制提取
            if word in dynamic_whitelist:
                extracted.add(word)
                continue
            # 提取名词和专有名词，过滤掉单字
            if token.pos_ in ["NOUN", "PROPN"] and len(word) > 1:
                extracted.add(word)

        return list(extracted)

extractor = IngredientExtractor()
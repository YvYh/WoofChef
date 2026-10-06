import spacy

class IngredientExtractor:
    def __init__(self):
        try:
            self.nlp = spacy.load("zh_core_web_sm")
        except Exception as e:
            print(f"NLP 模型加载失败，请确保在 Dockerfile 中执行了下载命令: {e}")
            self.nlp = None

    def extract(self, text):
        if not self.nlp or not text.strip(): return []
        doc = self.nlp(text)
        # 提取名词和专有名词，过滤掉单字
        res = [token.text for token in doc if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 1]
        return list(set(res))

extractor = IngredientExtractor()
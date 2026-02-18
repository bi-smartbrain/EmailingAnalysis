# %%
# # создание диапазонов на основе crash_ranges
# date_ranges = []
# for arange in crash_ranges:
#     item = {
#         'after_dt': arange[0],
#         'before_dt': arange[1],
#     }
#     date_ranges.append(item)
# %%
# # создание кастом диапазона
#
# st_dt = dt.datetime(year=2026, month=1, day=8, hour=0, minute=35, second=0, microsecond=0)
# en_dt = dt.datetime(year=2026, month=1, day=8, hour=0, minute=40, second=0, microsecond=0)
# date_ranges = [{
#         'after_dt': st_dt,
#         'before_dt': en_dt,
#     }]
# %%
#
#
# def extract_subject_key_improved(
#         subject: str,
#         known_phrases: Optional[List[str]] = None,
#         all_subjects: Optional[List[str]] = None,
#         min_phrase_words: int = 4,
#         min_percentage: float = 1.0,
#         min_absolute_count: int = 3,
#         prefer_shorter_common: bool = True  # Новый параметр!
# ) -> Optional[str]:
#     """
#     Извлекает ключевую фразу из темы письма.
#     prefer_shorter_common: если True, предпочитает более короткие общие фразы
#     """
#
#     @lru_cache(maxsize=10000)
#     def clean_text_cached(text: str) -> str:
#         """Очищает текст."""
#         text = re.sub(r'^(Re:|Fwd:|Fw:|🚀|📧|\s*[-–—|]*\s*)', '', text, flags=re.IGNORECASE)
#         text = re.sub(r'[|/\\–—]', ' ', text)
#         text = re.sub(r'\s+', ' ', text).strip().lower()
#         return text
#
#     def get_ngrams(text: str, min_n: int, max_n: int) -> List[str]:
#         """Генерирует n-граммы."""
#         words = text.split()
#         ngrams = []
#         for n in range(min_n, min(max_n, len(words)) + 1):
#             for i in range(len(words) - n + 1):
#                 ngram = ' '.join(words[i:i + n])
#                 ngrams.append(ngram)
#         return ngrams
#
#     # ШАГ 1: Очищаем тему
#     cleaned_subject = clean_text_cached(subject)
#     if not cleaned_subject:
#         return None
#
#     # ШАГ 2: Проверяем известные фразы
#     if known_phrases:
#         for phrase in known_phrases:
#             if clean_text_cached(phrase) in cleaned_subject:
#                 return phrase
#
#     # ШАГ 3: Находим ВСЕ подходящие фразы из частотных
#     if all_subjects:
#         cleaned_all = [clean_text_cached(s) for s in all_subjects if s]
#         total_subjects = len(cleaned_all)
#
#         # Динамический порог
#         dynamic_min_count = max(min_absolute_count, int(total_subjects * min_percentage / 100))
#
#         # Собираем и считаем n-граммы
#         all_ngrams = []
#         for s in cleaned_all:
#             ngrams = get_ngrams(s, min_phrase_words, min_phrase_words + 4)  # +4 для гибкости
#             all_ngrams.extend(ngrams)
#
#         ngram_counts = Counter(all_ngrams)
#
#         # Находим все фразы, которые подходят для текущей темы
#         candidate_phrases = []
#         for ngram, count in ngram_counts.items():
#             if count >= dynamic_min_count and ngram in cleaned_subject:
#                 candidate_phrases.append((ngram, count, len(ngram.split())))
#
#         # Если нашли кандидатов, выбираем лучшего
#         if candidate_phrases:
#             if prefer_shorter_common:
#                 # Сортируем: сначала по частоте, потом по длине (предпочитаем короче)
#                 candidate_phrases.sort(key=lambda x: (-x[1], x[2], x[0]))
#             else:
#                 # Сортируем: сначала по длине (предпочитаем длиннее), потом по частоте
#                 candidate_phrases.sort(key=lambda x: (-x[2], -x[1], x[0]))
#
#             best_phrase = candidate_phrases[0][0]
#             return ' '.join(word.capitalize() for word in best_phrase.split())
#
#     # Если ничего не нашли
#     return None
#
#
# def add_subject_key_into_emails(emails, known_phrases=None, update_phrases=False):
#     """
#     Ищет ключевые фразы в теме письма и добавляет ее в поле subject_key.
#     Инкрементально обновляет список известных фраз.
#
#     Args:
#         emails: список словарей с данными писем (должен содержать 'subject')
#         known_phrases: начальный список известных фраз (опционально)
#         update_phrases: обновлять ли список фраз в процессе (True по умолчанию)
#
#     Returns:
#         dict: {
#             'emails': список писем с добавленным 'subject_key',
#             'phrases': обновленный список известных фраз,
#             'phrase_stats': статистика по фразам (Counter),
#             'coverage': процент писем, получивших subject_key
#         }
#     """
#     if known_phrases is None:
#         known_phrases = []
#
#     # Создаем копию списка фраз для модификации
#     current_phrases = known_phrases.copy()
#     email_results = []
#     phrase_counter = Counter()
#
#     # Собираем все темы для анализа в extract_subject_key_improved
#     all_subjects = [email['subject'] for email in emails]
#
#     print(f"Обработка {len(emails)} писем...")
#     print(f"Начальный список фраз: {len(current_phrases)}")
#
#     for email in tqdm(emails, desc="Обработка писем"):
#         # Извлекаем ключевую фразу из темы
#         subject_key = extract_subject_key_improved(
#             subject=email['subject'],
#             known_phrases=current_phrases,
#             all_subjects=all_subjects,
#             min_phrase_words=4,
#             min_percentage=0.05,
#             min_absolute_count=2
#         )
#
#         # Добавляем результат к email
#         email_with_key = email.copy()  # Создаем копию, чтобы не модифицировать исходный
#         email_with_key['subject_key'] = subject_key
#         email_results.append(email_with_key)
#
#         # Обновляем статистику
#         if subject_key and subject_key != 'unknown':
#             phrase_counter[subject_key] += 1
#
#         # Инкрементально обновляем список фраз
#         if update_phrases and subject_key and subject_key != 'unknown':
#             if subject_key not in current_phrases:
#                 # Проверяем, не является ли новая фраза подфразой существующей
#                 is_subphrase = False
#                 for existing_phrase in current_phrases:
#                     if subject_key in existing_phrase or existing_phrase in subject_key:
#                         # Оставляем более длинную фразу
#                         if len(subject_key) > len(existing_phrase):
#                             current_phrases.remove(existing_phrase)
#                             current_phrases.append(subject_key)
#                             print(f"Обновлена фраза: '{existing_phrase}' → '{subject_key}'")
#                         is_subphrase = True
#                         break
#
#                 if not is_subphrase:
#                     current_phrases.append(subject_key)
#
#     # Сортируем фразы по частоте использования
#     sorted_phrases = sorted(current_phrases,
#                             key=lambda x: phrase_counter.get(x, 0),
#                             reverse=True)
#
#     # Вычисляем покрытие
#     emails_with_key = sum(1 for email in email_results
#                           if email.get('subject_key') and email['subject_key'] != 'unknown')
#     coverage = (emails_with_key / len(email_results)) * 100 if email_results else 0
#
#     print(f"\nРезультаты:")
#     print(f"- Обработано писем: {len(email_results)}")
#     print(f"- Писем с определенной темой: {emails_with_key} ({coverage:.1f}%)")
#     print(f"- Уникальных фраз: {len(sorted_phrases)}")
#     print(f"- Топ-5 фраз: {list(phrase_counter.most_common(5))}")
#
#     return {
#         'emails': email_results,
#         'phrases': sorted_phrases,
#         'phrase_stats': dict(phrase_counter.most_common()),
#         'coverage': coverage
#     }
#
#
# # обновленный список фраз сохраняем в БД и переиспользуем его на след.итерации
# updated_phrases = result['phrases']
# if len(updated_phrases) > len(known_phrases):
#     print(f"Новая ключевая фраза: {set(updated_phrases) - set(known_phrases)}")
#     phrases_df = pd.DataFrame(updated_phrases, columns=['key_phrase'])
#     save_df_to_db(phrases_df, "subject_key_phrases", mode="replace")
#     known_phrases = updated_phrases
#
#
# def get_leads_by_emails_dt(after_dt, before_dt, fields_lst=None, only_totals=False):
#     query_row = """{
#     "_limit": 200,
#     "query": {
#         "negate": false,
#         "queries": [
#             {
#                 "negate": false,
#                 "object_type": "lead",
#                 "type": "object_type"
#             },
#             {
#                 "negate": false,
#                 "queries": [
#                     {
#                         "negate": false,
#                         "related_object_type": "activity.email",
#                         "related_query": {
#                             "negate": false,
#                             "queries": [
#                                 {
#                                     "condition": {
#                                         "before": null,
#                                         "on_or_after": {
#                                             "type": "fixed_utc",
#                                             "value": "2025-12-08T21:12:12+00:00"
#                                         },
#                                         "type": "moment_range"
#                                     },
#                                     "field": {
#                                         "field_name": "date",
#                                         "object_type": "activity.email",
#                                         "type": "regular_field"
#                                     },
#                                     "negate": false,
#                                     "type": "field_condition"
#                                 },
#                                 {
#                                     "condition": {
#                                         "before": {
#                                             "type": "fixed_utc",
#                                             "value": "2025-12-09T21:12:12+00:00"
#                                         },
#                                         "on_or_after": null,
#                                         "type": "moment_range"
#                                     },
#                                     "field": {
#                                         "field_name": "date",
#                                         "object_type": "activity.email",
#                                         "type": "regular_field"
#                                     },
#                                     "negate": false,
#                                     "type": "field_condition"
#                                 }
#                             ],
#                             "type": "and"
#                         },
#                         "this_object_type": "lead",
#                         "type": "has_related"
#                     }
#                 ],
#                 "type": "and"
#             }
#         ],
#         "type": "and"
#     },
#     "results_limit": null,
#     "sort": [
#         {
#             "direction": "desc",
#             "field": {
#                 "field_name": "date_created",
#                 "object_type": "lead",
#                 "type": "regular_field"
#             }
#         }
#     ]
# }"""
#     after_dt -= dt.timedelta(hours=3)
#     before_dt -= dt.timedelta(hours=3)
#
#     after_str = after_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
#     before_str = before_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
#
#     query_row = query_row.replace("2025-12-08T21:12:12+00:00", after_str)
#     query_row = query_row.replace("2025-12-09T21:12:12+00:00", before_str)
#     query = json.loads(query_row)
#     if fields_lst:
#         query["_fields"] = {"lead": fields_lst}
#     resp = get_objects(query, only_totals=only_totals)
#     return resp
#
#
# def detect_lead_age(lead, email=None):
#     """Определяет возраст лида на основе даты его создания.
#         Возвращает словарь по форме {age_group: Новые, age_days: 27}"""
#
#     try:
#         # Парсим дату создания лида и добавляем 3 часа
#         lead_created_str = lead['date_created'].split('+')[0]
#         lead_created_dt = pd.to_datetime(lead_created_str)
#         lead_created_dt += dt.timedelta(hours=3)
#
#         # Определяем дату сравнения
#         compare_dt = dt.datetime.today()
#         if email:
#             compare_str = email['date_sent'].split('+')[0]
#             compare_dt = pd.to_datetime(compare_str)
#             compare_dt += dt.timedelta(hours=3)
#
#         # Сравниваем даты и определяем возрастную группу
#         days_diff = (compare_dt - lead_created_dt).days
#
#         if days_diff < 30:
#             age_group = "1.Молодые"
#         elif days_diff <= 365:
#             age_group = "2.Зрелые"
#         else:
#             age_group = "3.Старые"
#
#         return {'age_group': age_group, 'age_days': days_diff}
#
#     except Exception as e:
#         return f'Error: не удалось определить возраст лида: {str(e)}'
#
#
# def get_leads_from_query(query, skip=0, maximum=10000000000):
#     params = {
#         "query": query,
#         "_skip": skip,
#         "_limit": 100
#     }
#
#     leads = []
#     while True:
#         resp = f.api.get('lead', params=params)
#         leads.extend(resp['data'])
#         if resp['has_more'] and len(leads) < maximum:
#             params['_skip'] += params['_limit']
#             print(f'{len(leads)} лидов получено')
#         else:
#             print(f'Всего {len(leads)} лидов получено')
#             return leads
#
#
# def detect_primary_status(email: dict) -> str:
#     """
#     Определяет первичность письма.
#
#     Returns:
#         'primary', 'follow_up' или строка с ошибкой
#     """
#     try:
#         # 1. Проверка на главное письмо из сервиса рассылок
#         if email.get('created_by_name') is None:
#             return 'primary'
#
#         # 2. Обработка писем, отправленных из CRM
#         # а) Проверка followup_sequence_id
#         followup_seq_id = email.get('followup_sequence_id')
#         if followup_seq_id is not None and str(followup_seq_id).strip() != '':
#             return 'follow_up'
#
#         # б) Проверка ключевых слов в template_name
#         template_name = email.get('template_name', '')
#         if not isinstance(template_name, str):
#             template_name = str(template_name)
#
#         template_lower = template_name.lower()
#         follow_keywords = ['follow', 'пинок', 'fup']
#
#         for keyword in follow_keywords:
#             if keyword in template_lower:
#                 return 'follow_up'
#
#         # в) Проверка цифр 2-9 в начале или конце template_name
#         # Очищаем от лишних пробелов
#         template_clean = template_name.strip()
#
#         if template_clean:
#             # Проверяем начало строки
#             first_char = template_clean[0]
#             if first_char.isdigit() and '2' <= first_char <= '9':
#                 return 'follow_up'
#
#             # Проверяем конец строки
#             last_char = template_clean[-1]
#             if last_char.isdigit() and '2' <= last_char <= '9':
#                 return 'follow_up'
#
#         # Если ни одно условие для follow_up не сработало - это primary
#         return 'primary'
#
#     except Exception as e:
#         return f'Error: не удалось определить первичность письма: {str(e)}'
#
#
# def get_pre_sent_emails(email, lead):
#     """Получает предыдущие отправленные письма в лиде"""
#     after_str = "1990-01-01T00:00:00+00:00"
#     after_dt = dt.datetime.strptime(after_str, "%Y-%m-%dT%H:%M:%S+00:00")
#     before_dt = pd.to_datetime(email['date_sent'])
#     pre_sent_emails = get_sent_emails(after_dt, before_dt, lead_id=lead['id'])
#     return pre_sent_emails
#
#
# def find_common_patterns(all_subjects, min_count=5):
#     """Находит общие паттерны, игнорируя названия компаний."""
#
#     @lru_cache(maxsize=10000)
#     def clean_text(text: str) -> str:
#         text = re.sub(r'^(Re:|Fwd:|Fw:|🚀|📧|\s*[-–—|]*\s*)', '', text, flags=re.IGNORECASE)
#         text = re.sub(r'[|/\\–—]', ' ', text)
#         text = re.sub(r'\s+', ' ', text).strip().lower()
#         return text
#
#     # Собираем статистику по 3-словным фразам
#     all_3grams = []
#     for subject in all_subjects:
#         cleaned = clean_text(subject)
#         words = cleaned.split()
#         if len(words) >= 3:
#             for i in range(len(words) - 2):
#                 phrase = ' '.join(words[i:i + 3])
#                 all_3grams.append(phrase)
#
#     # Подсчитываем частоту
#     counter = Counter(all_3grams)
#
#     # Фильтруем и сортируем
#     common_phrases = []
#     for phrase, count in counter.items():
#         if count >= min_count:
#             # Проверяем, что это не фраза с именем компании
#             # (простейшая эвристика - не содержит 's, Ltd, Inc и т.д.)
#             if not any(x in phrase for x in ["'s", " ltd", " inc", " corp", " co", " llc"]):
#                 common_phrases.append((phrase, count))
#
#     # Сортируем по частоте
#     common_phrases.sort(key=lambda x: -x[1])
#
#     return [phrase.capitalize() for phrase, _ in common_phrases]
#
#

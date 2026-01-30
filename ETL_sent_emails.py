import pandas as pd
import datetime as dt
from functions import (load_df_from_db, get_sent_emails, add_subject_key_into_emails,
                       save_df_to_db, create_date_ranges)



# загружаем из БД даты отправленных писем (минимальную и максимальную)
query = """
SELECT 
    MIN(date_sent) as min_date,
    MAX(date_sent) as max_date
FROM sent_emails
WHERE date_sent IS NOT NULL
"""
df = load_df_from_db(table_name='sent_emails', query=query)
min_date_sent_in_db = df['min_date'][0]
max_date_sent_in_db = df['max_date'][0] 
print(f"{min_date_sent_in_db = }\n{max_date_sent_in_db = }")


# Создаем диапазоны дат для обновления отчета вперед
today = dt.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
start_dt = max_date_sent_in_db + dt.timedelta(seconds=1)
end_dt = today
date_ranges = create_date_ranges(start_dt, end_dt, interval_min=5)


# загружаем из БД список известных ключевых фраз
phrases_df = load_df_from_db('subject_key_phrases')
known_phrases = phrases_df['key_phrase'].to_list()


# получаем и обрабатываем письма в каждом из диапазонов
fields = ['id', 'date_sent', 'subject', 'body_text', 'sender', 'created_by_name', 'date_created',
          'lead_id', 'sequence_name', 'template_name', 'in_reply_to_id', 'has_reply']
range_cnt = 1
failed_ranges = set()
for date_range in date_ranges:
    after_dt, before_dt = date_range['after_dt'], date_range['before_dt']
    try:
        print(f"\nДиапазон: {range_cnt} из {len(date_ranges)}"
              f"\nЗагружаем отправленные письма за период: {after_dt} - {before_dt}")
              
        emails = get_sent_emails(after_dt, before_dt, fields_lst=fields)
        result = add_subject_key_into_emails(emails, known_phrases=known_phrases)
        processed_emails = result['emails']
        
        # обновленный список фраз сохраняем в БД и переиспользуем его на след.итерации
        updated_phrases = result['phrases']    
        if len(updated_phrases) > len(known_phrases):
            print(f"Новая ключевая фраза: {set(updated_phrases) - set(known_phrases)}")
            phrases_df = pd.DataFrame(updated_phrases, columns=['key_phrase'])
            save_df_to_db(phrases_df, "subject_key_phrases", mode="replace")
            known_phrases = updated_phrases
        
        # сохраняем в БД обработанные письма, приводя даты к МСК времени    
        df = pd.DataFrame(processed_emails)
        df['date_created'] = df['date_created'].str[:19]
        df['date_created'] = pd.to_datetime(df['date_created']) + dt.timedelta(hours=3)
        df['date_sent'] = df['date_sent'].str[:19]
        df['date_sent'] = pd.to_datetime(df['date_sent']) + dt.timedelta(hours=3)
        
        # df['subject_key'].value_counts().reset_index()
        save_df_to_db(df, "sent_emails", mode="append")
    except Exception as e:
        failed_ranges.add((after_dt, before_dt)) 
        print(f"Ошибка при обработке диапазона: {e}")
    
    print(f"Количество не сохранившихся диапазонов: {len(failed_ranges)}")
    range_cnt += 1

    
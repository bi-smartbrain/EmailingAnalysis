import json
import functions as f
import pandas as pd
import datetime as dt

##########################################################################
# ETL-процесс для отправленных писем, на которые был ответ (has_reply=True)
##########################################################################


def etl_answered_emails():
    # запрашиваем отправленные письма из Close за последние 14 дней с пометкой has_reply=True
    query_row = """
    {
        "_limit": 200,
        "query": {
            "negate": false,
            "queries": [
                {
                    "negate": false,
                    "object_type": "activity.email",
                    "type": "object_type"
                },
                {
                    "negate": false,
                    "queries": [
                        {
                            "negate": false,
                            "queries": [
                                {
                                    "condition": {
                                        "type": "boolean",
                                        "value": true
                                    },
                                    "field": {
                                        "field_name": "has_reply",
                                        "object_type": "activity.email",
                                        "type": "regular_field"
                                    },
                                    "negate": false,
                                    "type": "field_condition"
                                },
                                {
                                    "condition": {
                                        "type": "term",
                                        "values": [
                                            "sent"
                                        ]
                                    },
                                    "field": {
                                        "field_name": "status",
                                        "object_type": "activity.email",
                                        "type": "regular_field"
                                    },
                                    "negate": false,
                                    "type": "field_condition"
                                }
                            ],
                            "type": "and"
                        },
                        {
                            "negate": false,
                            "queries": [
                                {
                                    "condition": {
                                        "before": null,
                                        "on_or_after": {
                                            "direction": "past",
                                            "moment": {
                                                "type": "now"
                                            },
                                            "offset": {
                                                "days": 14,
                                                "hours": 0,
                                                "minutes": 0,
                                                "months": 0,
                                                "seconds": 0,
                                                "weeks": 0,
                                                "years": 0
                                            },
                                            "type": "offset",
                                            "which_day_end": "start"
                                        },
                                        "type": "moment_range"
                                    },
                                    "field": {
                                        "field_name": "date_sent",
                                        "object_type": "activity.email",
                                        "type": "regular_field"
                                    },
                                    "negate": false,
                                    "type": "field_condition"
                                }
                            ],
                            "type": "and"
                        }
                    ],
                    "type": "and"
                }
            ],
            "type": "and"
        },
        "results_limit": null,
        "sort": [
            {
                "direction": "desc",
                "field": {
                    "field_name": "date_created",
                    "object_type": "activity.email",
                    "type": "regular_field"
                }
            }
        ]
    }
    """
    fields = ['id', 'date_sent', 'subject', 'body_text', 'sender', 'created_by_name', 'date_created',
              'lead_id', 'sequence_name', 'template_name', 'in_reply_to_id', 'has_reply']
    query = json.loads(query_row)
    emails = f.get_objects(query, fields_lst=fields)

    # загружаем из БД список известных ключевых фраз
    phrases_df = f.load_df_from_db('subkeys_to_branch')
    known_phrases = phrases_df['subject_key'].to_list()

    # помечаем письма ключевой фразой
    processed_emails = f.add_subject_key_into_emails(emails, known_phrases=known_phrases)

    # сохраняем в БД письма, приводя даты к МСК времени
    df = pd.DataFrame(processed_emails)
    df = f.df_columns_add_hours(df=df)
    f.save_df_to_db(df, "answered_emails", mode="replace")


if __name__ == '__main__':
    etl_answered_emails()
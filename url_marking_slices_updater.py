#%%
import json
from tqdm import tqdm
import functions as f
#%%
import datetime as dt
def create_dates(depth_days=14, include_today=False):
    dates_list = []
    today = dt.date.today()
    
    stop_flag = 0 if include_today else 1
    while depth_days >= stop_flag:
        day = today - dt.timedelta(days=depth_days)
        day_str = day.strftime("%Y-%m-%d")
        dates_list.append(day_str)
        depth_days -= 1
        
    return dates_list


#%%
spread_name = "Анализ ежедневной отправки"
sheet_name = "markingRegs_imp"
dates = create_dates(depth_days=14, include_today=False)
#%%
# запрос тоталов в разрезе дней
print("запрос тоталов в разрезе дней")
days_report = [['date', 'total_emails']]
for date_sent in tqdm(dates):
    query_row = """
    {
    "limit": null,
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
                            },
                            {
                                "condition": {
                                    "before": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "end"
                                    },
                                    "on_or_after": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "start"
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
    query_row = query_row.replace("{email_date_sent}", date_sent)
    query = json.loads(query_row)
    total_emails = f.get_objects(query, only_totals=True)
    days_report_row = [date_sent, total_emails]
    days_report.append(days_report_row)

f.write_spread_sheet(spread_name, "email_days_pyReport", days_report)
#%%
# получение разметки по цепочкам
print("получение разметки по цепочкам")
seqs_range = f.get_sheet_range(spread_name, sheet_name, "A2:C")
seqs = [{"seq_id": item[0], "seq_name": f'{item[2]} → ({item[1]})'} for item in seqs_range if item != '']
#%%
#определяем список цепочек, которые использовались в отчетном периоде
print("определяем список ID-цепочек, которые использовались в отчетном периоде")
used_seqs = []   
for seq in tqdm(seqs):
    query_row = """
{
    "limit": null,
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
                                    "mode": "exact_value",
                                    "type": "text",
                                    "value": "{mark_item_id}"
                                },
                                "field": {
                                    "field_name": "body_text",
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
                            },
                            {
                                "condition": {
                                    "before": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent_before}",
                                        "which": "end"
                                    },
                                    "on_or_after": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent_after}",
                                        "which": "start"
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
    query_row = query_row.replace("{mark_item_id}", seq['seq_id'])
    query_row = query_row.replace("{email_date_sent_after}", dates[0])
    query_row = query_row.replace("{email_date_sent_before}", dates[-1])
    query = json.loads(query_row)
    total_emails_for_all_dates = f.get_objects(query, only_totals=True)
    if total_emails_for_all_dates:
        used_seqs.append(seq)

print(f'Всего используемых цепочек: {len(used_seqs)}')
    

#%%
# запрос тоталов по используемым цепочкам
print("запрос тоталов по используемым цепочкам")
seq_report = [['seq_id', 'seq_name', 'date_sent', 'total_emails']]
for seq in tqdm(used_seqs):
    for date_sent in dates:
        query_row = """
{
    "limit": null,
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
                                    "mode": "exact_value",
                                    "type": "text",
                                    "value": "{mark_item_id}"
                                },
                                "field": {
                                    "field_name": "body_text",
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
                            },
                            {
                                "condition": {
                                    "before": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "end"
                                    },
                                    "on_or_after": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "start"
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
        query_row = query_row.replace("{mark_item_id}", seq['seq_id'])
        query_row = query_row.replace("{email_date_sent}", date_sent)
        query = json.loads(query_row)
        total_emails = f.get_objects(query, only_totals=True)
        seq_report_row = [seq['seq_id'], seq['seq_name'], date_sent, total_emails]
        seq_report.append(seq_report_row)

f.write_spread_sheet(spread_name, "mark_seq_report", seq_report)
#%%
# получение разметки по направлениям
print("получение разметки по направлениям")
directions_range = f.get_sheet_range(spread_name, sheet_name, "H2:J")
directions = [{"direction_id":item[0], "direction_name":item[1]} for item in directions_range if item != '']
#%%
#определяем список направлений, которые использовались в отчетном периоде
print("определяем список направлений, которые использовались в отчетном периоде")
used_directions = []   
for direction in tqdm(directions):
    query_row = """
{
    "limit": null,
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
                                    "mode": "exact_value",
                                    "type": "text",
                                    "value": "{mark_item_id}"
                                },
                                "field": {
                                    "field_name": "body_text",
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
                            },
                            {
                                "condition": {
                                    "before": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent_before}",
                                        "which": "end"
                                    },
                                    "on_or_after": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent_after}",
                                        "which": "start"
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
    query_row = query_row.replace("{mark_item_id}", direction['direction_id'])
    query_row = query_row.replace("{email_date_sent_after}", dates[0])
    query_row = query_row.replace("{email_date_sent_before}", dates[-1])
    query = json.loads(query_row)
    total_emails_for_all_dates = f.get_objects(query, only_totals=True)
    if total_emails_for_all_dates:
        used_directions.append(direction)

print(f'Всего используемых направлений: {len(used_directions)}')
#%%
# запрос тоталов по направлениям
print("запрос тоталов по направлениям")
direction_report = [['direction_id', 'direction_name', 'date_sent', 'total_emails']]
for direction in tqdm(used_directions):
    for date_sent in dates:
        query_row = """
{
    "limit": null,
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
                                    "mode": "exact_value",
                                    "type": "text",
                                    "value": "{mark_item_id}"
                                },
                                "field": {
                                    "field_name": "body_text",
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
                            },
                            {
                                "condition": {
                                    "before": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "end"
                                    },
                                    "on_or_after": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "start"
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
        query_row = query_row.replace("{mark_item_id}", direction['direction_id'])
        query_row = query_row.replace("{email_date_sent}", date_sent)
        query = json.loads(query_row)
        total_emails = f.get_objects(query, only_totals=True)
        direction_report_row = [direction['direction_id'], direction['direction_name'], date_sent, total_emails]
        direction_report.append(direction_report_row)

f.write_spread_sheet(spread_name, "mark_direction_report", direction_report)
#%%
# получение разметки по шагам
print("получение разметки по шагам")
steps_range = f.get_sheet_range(spread_name, sheet_name, "L2:M")
steps = [{"step_id":item[0], "step_num":item[1]} for item in steps_range if item != '']
#%%
#определяем список шагов, которые использовались в отчетном периоде
print("определяем список шагов, которые использовались в отчетном периоде")
used_steps = []   
for step in tqdm(steps):
    query_row = """
{
    "limit": null,
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
                                    "mode": "exact_value",
                                    "type": "text",
                                    "value": "{mark_item_id}"
                                },
                                "field": {
                                    "field_name": "body_text",
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
                            },
                            {
                                "condition": {
                                    "before": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent_before}",
                                        "which": "end"
                                    },
                                    "on_or_after": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent_after}",
                                        "which": "start"
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
    query_row = query_row.replace("{mark_item_id}", step['step_id'])
    query_row = query_row.replace("{email_date_sent_after}", dates[0])
    query_row = query_row.replace("{email_date_sent_before}", dates[-1])
    query = json.loads(query_row)
    total_emails_for_all_dates = f.get_objects(query, only_totals=True)
    if total_emails_for_all_dates:
        used_steps.append(step)

print(f'Всего используемых шагов: {len(used_steps)}')
#%%
# запрос тоталов по шагам
print("запрос тоталов по шагам")
step_report = [['step_id', 'step_num', 'date_sent', 'total_emails']]
for step in tqdm(used_steps):
    for date_sent in dates:
        query_row = """
{
    "limit": null,
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
                                    "mode": "exact_value",
                                    "type": "text",
                                    "value": "{mark_item_id}"
                                },
                                "field": {
                                    "field_name": "body_text",
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
                            },
                            {
                                "condition": {
                                    "before": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "end"
                                    },
                                    "on_or_after": {
                                        "type": "fixed_local_date",
                                        "value": "{email_date_sent}",
                                        "which": "start"
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
        query_row = query_row.replace("{mark_item_id}", step['step_id'])
        query_row = query_row.replace("{email_date_sent}", date_sent)
        query = json.loads(query_row)
        total_emails = f.get_objects(query, only_totals=True)
        step_report_row = [step['step_id'], step['step_num'], date_sent, total_emails]
        step_report.append(step_report_row)

f.write_spread_sheet(spread_name, "mark_step_report", step_report)
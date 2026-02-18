from functions import load_df_from_db, write_spread_sheet, df_to_sheets_report

######################################################################################
# Модуль экспорта данных из Метабейз в отчет Анализ ежедневной отправки
# (таблица кол-во писем в разрезе тем по дням)
#####################################################################################


def mtb_export():
    sql_query = """
    SELECT
        TO_CHAR(DATE_TRUNC('day', se.date_sent), 'YYYY-MM-DD') AS date_sent,
        se.subject_key AS subject_key,
        COUNT(DISTINCT se.id) AS count
    FROM
        public.sent_emails se
        LEFT JOIN public.subkeys_to_branch stb ON se.subject_key = stb.subject_key
    WHERE
        se.date_sent >= CURRENT_DATE - INTERVAL '14 days'
        AND se.date_sent < CURRENT_DATE
    GROUP BY
        TO_CHAR(DATE_TRUNC('day', se.date_sent), 'YYYY-MM-DD'),
        se.subject_key
    """
    df = load_df_from_db(table_name='sent_emails', query=sql_query)

    report = df_to_sheets_report(df)
    spread_name = "Анализ ежедневной отправки"
    sheet_name = "daily_subkeys_mtb_imp"
    write_spread_sheet(spread=spread_name, sheet=sheet_name, report=report)


if __name__ == '__main__':
    mtb_export()
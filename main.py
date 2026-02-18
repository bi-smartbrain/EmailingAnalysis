from ETL_sent_emails import etl_sent_emails
from ETL_answered_emails import etl_answered_emails
from mtb_export import mtb_export
from subkey_branch_updater import subkey_branch_updater


####################################################################
# актуализация отчета Анализ ежедневной отправки
# и метабейз-дашборда Анализ емейлинга
#####################################################################


etl_sent_emails()
mtb_export()
etl_answered_emails()


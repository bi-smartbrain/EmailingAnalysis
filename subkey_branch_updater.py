import pandas as pd
from functions import get_sheet_range, save_df_to_db

####################################################################
### Обновляет в БД таблицу сопоставления ключевых фраз с бренчами
### данными из гугл-таблицы
####################################################################


def subkey_branch_updater():
    spread_name = "Анализ ежедневной отправки"
    sheet_name = "subkeys_to_branch"
    subkey_to_branch_table = get_sheet_range(spread_name, sheet_name, "A:C")

    subkey_to_branch_df = pd.DataFrame(subkey_to_branch_table[1:], columns=subkey_to_branch_table[0])
    save_df_to_db(subkey_to_branch_df, "subkeys_to_branch", mode="replace")


if __name__ == "__main__":
    subkey_branch_updater()

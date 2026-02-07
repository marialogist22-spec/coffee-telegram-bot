import pandas as pd
import matplotlib.pyplot as plt

# Загружаем данные
df = pd.read_csv("data.csv", names=["user_id", "machine_code", "type", "value"])

# Фильтруем оценки кофе
coffee = df[df['type'] == 'coffee']
service = df[df['type'] == 'service']
issues = df[df['type'] == 'issue']

# ---------------- График оценки кофе ----------------
if not coffee.empty:
    coffee['value'] = coffee['value'].astype(int)  # <-- преобразуем сразу весь столбец в int
    coffee_avg = coffee.groupby("machine_code")['value'].mean()
    coffee_avg.plot(kind='bar', title='Средняя оценка кофе', ylabel='Оценка')
    plt.savefig("coffee_rating.png")
    plt.show()

# ---------------- График оценки сервиса ----------------
if not service.empty:
    service['value'] = service['value'].astype(int)  # <-- тоже преобразуем
    service_avg = service.groupby("machine_code")['value'].mean()
    service_avg.plot(kind='bar', title='Средняя оценка сервиса', ylabel='Оценка', color='orange')
    plt.savefig("service_rating.png")
    plt.show()

# ---------------- Статистика проблем ----------------
if not issues.empty:
    issues_count = issues.groupby("value")['value'].count()
    issues_count.plot(kind='bar', title='Количество проблем', ylabel='Количество', color='red')
    plt.savefig("issues_count.png")
    plt.show()

# ---------------- Сохраняем в Excel ----------------
with pd.ExcelWriter("report.xlsx") as writer:
    coffee.to_excel(writer, sheet_name="Coffee")
    service.to_excel(writer, sheet_name="Service")
    issues.to_excel(writer, sheet_name="Issues")

print("Отчёт создан: report.xlsx + графики png")

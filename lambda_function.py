import boto3
import os
from datetime import datetime, timedelta, date

def lambda_handler(event, context):
    ce = boto3.client('ce')
    sns = boto3.client('sns')

    # 今月の合計請求額を取得
    total_billing = get_total_billing(ce)
    # 今月の合計請求額を取得（サービス毎）
    service_billings = get_service_billings(ce)
    # 昨日の請求額を取得
    today_billing = get_today_billing(ce)
    today_service_billings = get_today_service_billings(ce)

    # Amazon SNSトピックに発行するメッセージを生成
    (subject, message) = get_message(today_billing, total_billing, service_billings, today_service_billings)

    topic_arn =  os.environ['TOPIC_ARN']

    response = sns.publish(
        TopicArn = topic_arn,
        Subject = subject,
        Message = message
    )

    return response

def get_today_billing(ce):
    (start_date, end_date) = get_total_cost_date_range()

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Metrics=[
            'AmortizedCost'
        ]
    )

    return {
        'start': response['ResultsByTime'][0]['TimePeriod']['Start'],
        'end': response['ResultsByTime'][0]['TimePeriod']['End'],
        'billing': response['ResultsByTime'][-1]['Total']['AmortizedCost']['Amount'],
        'yesterday_billing': response['ResultsByTime'][-2]['Total']['AmortizedCost']['Amount']
    }

def get_total_billing(ce):
    (start_date, end_date) = get_total_cost_date_range()

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost'
        ]
    )

    return {
        'start': response['ResultsByTime'][0]['TimePeriod']['Start'],
        'end': response['ResultsByTime'][0]['TimePeriod']['End'],
        'billing': response['ResultsByTime'][0]['Total']['AmortizedCost']['Amount'],
    }


def get_service_billings(ce):
    (start_date, end_date) = get_total_cost_date_range()

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metrics=[
            'AmortizedCost'
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ]
    )

    billings = []

    for item in response['ResultsByTime'][0]['Groups']:
        billings.append({
            'service_name': item['Keys'][0],
            'billing': item['Metrics']['AmortizedCost']['Amount']
        })

    return billings

def get_today_service_billings(ce):
    (start_date, end_date) = get_total_cost_date_range()

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Metrics=[
            'AmortizedCost'
        ],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ]
    )

    billings = []

    for item in response['ResultsByTime'][-1]['Groups']:
        billings.append({
            'service_name': item['Keys'][0],
            'billing': item['Metrics']['AmortizedCost']['Amount']
        })

    return billings


def get_total_cost_date_range():
    start_date = date.today().replace(day=1).isoformat()
    end_date = date.today().isoformat()

    # get_cost_and_usage()のstartとendに同じ日付は指定不可のため、今日が1日なら「先月1日から今月1日（今日）」までの範囲にする
    if start_date == end_date:
        end_of_month = datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=-1)
        begin_of_month = end_of_month.replace(day=1)
        return begin_of_month.date().isoformat(), end_date
    return start_date, end_date


def get_message(today_billing, total_billing, service_billings, today_service_billings):
    start = datetime.strptime(total_billing['start'], '%Y-%m-%d').strftime('%Y/%m/%d')

    # Endの日付は結果に含まないため、表示上は前日にしておく
    end_today = datetime.strptime(total_billing['end'], '%Y-%m-%d')
    end_yesterday = (end_today - timedelta(days=1)).strftime('%Y/%m/%d')

    total = round(float(total_billing['billing']), 2)
    today = round(float(today_billing['billing']), 2)
    yesterday = round(float(today_billing['yesterday_billing']), 2)
    difference = round(today - yesterday,2)
    account_id = os.environ['ACCOUNT_ID']
    subject = f'アカウント({account_id})の昨日までの請求額：{total:.2f}USD(昨日の請求{today}USD)'

    message = []
    message.append(f'昨日の請求額:{today}USD、' + "\n" +  f'一昨日の請求額:{yesterday}USD、' + "\n" + f'昨日と一昨日の差額:{difference}USD' + "\n" + f'{start}～{end_yesterday}までの請求額:{total}USDです。' + "\n" + '【内訳】')
    for item in service_billings:
        service_name = item['service_name']
        billing = round(float(item['billing']), 2)

        if billing == 0.0:
            # 請求無しの場合は内訳を表示しない
            continue
        message.append(f'・{service_name}: ${billing:.2f}')

    message.append('【昨日の内訳】')

    for item in today_service_billings:
        service_name = item['service_name']
        billing = round(float(item['billing']), 2)

        if billing == 0.0:
            # 請求無しの場合は内訳を表示しない
            continue
        message.append(f'・{service_name}: ${billing:.2f}')

    return subject, '\n'.join(message)

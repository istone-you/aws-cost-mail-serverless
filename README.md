# aws-cost-mail-serverless
毎日14時にAWSの利用料金をメールで通知するLambdaを作成する構成を構築するServerless Frameworkのファイルです。

<img width="500" alt="CostMail.drawio.png" src="CostMail.drawio.png">

.envファイルを作成して下記変数の指定が必要です。
- SNS_MAIL = "<メールアドレス>"
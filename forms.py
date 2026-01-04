from flask_wtf import FlaskForm
from wtforms import (
    StringField, IntegerField, TextAreaField,
    SubmitField, DateField, SelectField
)
from wtforms.validators import DataRequired

#フォームを分けないと入力情報の不備でDB登録処理がスキップされる

# トップページ会社登録用フォーム
class RegistForm(FlaskForm):
    name = StringField('会社名', validators=[DataRequired('入力必須です')])
    industry = StringField('業界')
    url = StringField('マイページULR')
    submit = SubmitField('登録')

# 詳細ページ基本情報編集用フォーム
class EditForm(RegistForm): # RegistFormを継承して他の要素も使えるようにする
    entry_date = DateField('エントリー日')
    status = SelectField('現在の選考状況', choices=[('選考中'),('内々定'),('お祈り'),('辞退')])
    phase = StringField('選考フェーズ')
    change = SubmitField('保存して戻る')

# 詳細ページ詳細情報編集用フォーム
class DetailForm(FlaskForm):
    interest = IntegerField('志望度')
    memo = TextAreaField('会社情報メモ')
    edit = SubmitField('詳細編集')
    toTopPage = SubmitField('保存して戻る')

# スケジュール入力フォーム
class ScheduleForm(FlaskForm):
    event_name = StringField('イベント名', validators=[DataRequired()])
    event_content = StringField('内容')
    event_date = DateField('日付')
    event_memo = TextAreaField('メモ')
    submit = SubmitField('イベントを追加')
    change = SubmitField('保存して戻る')
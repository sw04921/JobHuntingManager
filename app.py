import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, MetaData
from flask_migrate import Migrate

app = Flask(__name__)

app.config['SECRET_KEY'] = os.urandom(24)
base_dir = os.path.dirname(__file__)
database = 'sqlite:///' + os.path.join(base_dir, 'data.sqlite')
app.config['SQLALCHEMY_DATABASE_URI'] = database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
Migrate(app, db, render_as_batch=True)

#===================================
#------------- モデル ---------------
#===================================

## 企業情報テーブル
class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)    # ID
    name = db.Column(db.String(64), nullable=False) # 企業名
    industry = db.Column(db.String(64))             # 業界
    url = db.Column(db.String(128))                 # マイページURL
    interest = db.Column(db.Integer)                # 志望度
    memo = db.Column(db.Text)                       # メモ
    # リレーション　選考状況テーブル　１対１
    selection = db.relationship("Selection", backref='company', uselist=False)
    # リレーション　スケジュールテーブル　１対多
    schedules = db.relationship("Schedule", backref='company')

## 選考状況テーブル
class Selection(db.Model):
    __tablename__ = 'selections'
    id = db.Column(db.Integer, primary_key=True)                    # ID
    company_id = db.Column(db.Integer, ForeignKey('companies.id'))  # 外部キー
    entry_date = db.Column(db.Date())                               # エントリー日
    status = db.Column(db.String(64))                               # 状況
    phase = db.Column(db.String(64))                                # 選考フェーズ

## スケジュールテーブル
class Schedule(db.Model):
    __tablename__ = 'schedules'                                      
    id = db.Column(db.Integer, primary_key=True)                    # ID
    company_id = db.Column(db.Integer, ForeignKey('companies.id'))  # 外部キー
    event_name = db.Column(db.String(128))                          # イベント名
    event_content = db.Column(db.Text)                              # イベント内容
    event_date = db.Column(db.Date())                               # イベント日
    event_memo = db.Column(db.Text)                                 # メモ

#=========================================
#------------- ルーティング ---------------
#=========================================
from forms import RegistForm, EditForm, DetailForm, ScheduleForm

# トップページ　表示
@app.route('/', methods=['GET', 'POST'])
def index():
    regist_form = RegistForm()
    sort_mode = request.args.get('sort')
    if sort_mode == 'interest':
        # 志望度順に並び替え　.desc()で降順にする
        companies = Company.query.order_by(Company.interest.desc()).all()
    else:
        companies = Company.query.all()
    # POST
    if regist_form.validate_on_submit(): # requeset.method == "POST" and form.validate()と同じ意味
        new_company = Company(name=regist_form.name.data, industry=regist_form.industry.data, url=regist_form.url.data)
        db.session.add(new_company)
        db.session.commit()
        # REDIRECT
        return redirect(url_for('index', _anchor=('regist_new_company')))
    # GET
    return render_template('top_list.html', companies=companies, regist_form=regist_form)
### PRGパターン
### redirectがないと二重にPOSTされる可能性がある。
### redirectを書かなかったとき、フォームに入力後エンターキーを押したらDBに登録されたが表示はされなかった。
### そのあともう一度登録ボタンを押すと、二重にPOSTされる。

# 詳細ページ　表示
@app.route('/detail/<int:id>', methods=['GET', 'POST'])
def show_detail(id):
    target = Company.query.filter_by(id=id).first()
    info_form = DetailForm(obj=target, prefix="info") # DBに登録された情報をフォームの初期値とする
    schedule_form = ScheduleForm(prefix="schedule")
    # POST　詳細フォーム
    if info_form.toTopPage.data and info_form.validate_on_submit(): # バリデーションOKであることを確認する
        target.interest = info_form.interest.data
        target.memo = info_form.memo.data
        db.session.commit()
        # REDIRECT
        return redirect(url_for('index'))
    # POST スケジュール
    if schedule_form.submit.data and schedule_form.validate_on_submit(): # どのボタンが押されたかを判断できるようにする
        new_schedule = Schedule(
            company_id=target.id,
            event_name=schedule_form.event_name.data,
            event_content=schedule_form.event_content.data,
            event_date=schedule_form.event_date.data,
            event_memo=schedule_form.event_memo.data
        )
        db.session.add(new_schedule)
        db.session.commit()
        # REDIRECT
        return redirect(url_for('show_detail', id=id, _anchor='add-event'))
    #GET
    return render_template('detail.html', company=target, info_form=info_form, schedule_form=schedule_form)

# 会社情報削除処理
@app.route('/delete/<int:id>', methods=['POST'])
def delete_company(id):
    target = Company.query.filter_by(id=id).first()
    db.session.delete(target)
    db.session.commit()
    return redirect(url_for('index'))

# イベント情報削除処理
@app.route('/schedule/delete/<int:id>', methods=['POST'])
def delete_event(id):
    target = Schedule.query.filter_by(id=id).first()
    company_id = target.company_id
    db.session.delete(target)
    db.session.commit()
    return redirect(url_for('show_detail', id=company_id, _anchor='event_list'))

# 基本情報編集
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_company(id):
    target = Company.query.filter_by(id=id).first()
    edit_form = EditForm(obj=target) # DBに登録された情報をフォームの初期値とする
    # POST
    if edit_form.validate_on_submit():
        target.name = edit_form.name.data
        target.industry = edit_form.industry.data
        target.url = edit_form.url.data
        # 選考データがなければ新しく作る
        if target.selection is None:
            target.selection = Selection()
        target.selection.entry_date=edit_form.entry_date.data
        target.selection.status=edit_form.status.data
        target.selection.phase=edit_form.phase.data
        db.session.commit()
        # REDIRECT
        return redirect(url_for('show_detail', id=id))
    # GET
    if request.method == 'GET':
        # 編集ページでフォームの初期値を設定するため、Selection情報が存在する場合のみセットする
        if target.selection:
            edit_form.entry_date.data = target.selection.entry_date
            edit_form.status.data = target.selection.status
            edit_form.phase.data = target.selection.phase
    return render_template('edit_info.html', edit_form=edit_form, company=target)

@app.route('/schedule/edit/<int:id>', methods=['GET', 'POST'])
def edit_event(id):
    target = Schedule.query.filter_by(id=id).first()
    schedule_form = ScheduleForm(obj=target) # DBに登録された情報をフォームの初期値とする
    # POST
    if schedule_form.validate_on_submit():
        target.event_name = schedule_form.event_name.data
        target.event_content = schedule_form.event_content.data
        target.event_date = schedule_form.event_date.data
        target.event_memo = schedule_form.event_memo.data
        db.session.commit()
        # REDIRECT
        return redirect(url_for('show_detail', id=target.company_id))
    # GET
    return render_template('edit_schedule.html', schedule_form=schedule_form)


if __name__ == '__main__':
    app.run()
import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, MetaData
from flask_migrate import Migrate
from datetime import date
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

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

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

#===================================
#------------- モデル ---------------
#===================================

## ユーザーデータベース
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

## 企業情報テーブル
class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)            # ID
    user_id = db.Column(db.Integer, ForeignKey('user.id'))  #ユーザー判別用ID
    name = db.Column(db.String(64), nullable=False)         # 企業名
    industry = db.Column(db.String(64))                     # 業界
    url = db.Column(db.String(128))                         # マイページURL
    interest = db.Column(db.Integer)                        # 志望度
    memo = db.Column(db.Text)                               # メモ
    next_deadline = db.Column(db.Date())                    # 次回期限
    # リレーション　選考状況テーブル　１対１
    selection = db.relationship("Selection", backref='company', uselist=False)
    # リレーション　スケジュールテーブル　１対多
    schedules = db.relationship("Schedule", backref='company', order_by="desc(Schedule.event_date)")

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
from forms import RegistForm, EditForm, DetailForm, ScheduleForm, AuthForm, UserSettingsForm

# ユーザーIDからユーザー情報を取得
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    auth_form = AuthForm()
    if auth_form.validate_on_submit():
        username = auth_form.username.data
        password = auth_form.password.data
        # 同名のユーザーがいないかチェック
        user = User.query.filter_by(username=username).first()
        if user:
            flash('そのユーザー名は既に使用されています')
            return redirect(url_for('signup'))
        # パスワードを暗号化して保存
        new_user = User(username=username, password=generate_password_hash(password, method='scrypt'))
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html', auth_form=auth_form)

# ログイン
@app.route('/login', methods=['GET', 'POST'])
def login():
    auth_form = AuthForm()
    if auth_form.validate_on_submit():
        username = auth_form.username.data
        password = auth_form.password.data
        user = User.query.filter_by(username=username).first()
        # ユーザーが存在し、パスワードが合致する場合
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('ユーザー名またはパスワードが間違っています')
    return render_template('login.html', auth_form=auth_form)

# ログアウト
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ユーザー設定
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = UserSettingsForm()
    
    if form.validate_on_submit():
        # ユーザー名変更
        if form.username.data:
            # 他の人と重複していないか確認（自分自身の名前は可）
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user and existing_user.id != current_user.id:
                flash('そのユーザー名は既に使用されています')
                return redirect(url_for('settings'))
            current_user.username = form.username.data
        
        # パスワード変更（入力がある場合のみ）
        if form.new_password.data:
            current_user.password = generate_password_hash(form.new_password.data, method='scrypt')
            
        db.session.commit()
        flash('ユーザー情報を更新しました')
        return redirect(url_for('index'))

    # 初期値として現在のユーザー名を入れる
    if request.method == 'GET':
        form.username.data = current_user.username

    return render_template('settings.html', form=form)

# トップページ　表示
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    regist_form = RegistForm()
    sort_mode = request.args.get('sort')
    filter_industry = request.args.get('industry')
    # 自身のIDのデータだけ集める
    base_query = Company.query.filter_by(user_id=current_user.id)
    all_companies = base_query.all()
    # 存在する企業名の配列を作成　すべての企業からNone以外を集めて、set()で重複を削除、listで配列に戻して、sortedで並べ替え
    # 並べ替えるとページ更新時に見やすくなる
    industries = sorted(list(set([c.industry for c in all_companies if c.industry])))
    query = base_query
    if filter_industry:
        # 業界で絞り込み
        query = query.filter(Company.industry == filter_industry)
    if sort_mode == 'interest':
        # 志望度順に並び替え　.desc()で降順にする
        query = query.order_by(Company.interest.desc())
    elif sort_mode == 'deadline':
        # 期限順に並び替え　今日の日付を取得して、それより後の日付だけを抽出、そこから並び替える
        query = query.filter(Company.next_deadline >= date.today()).order_by(Company.next_deadline)
    companies = query.all()
    # POST
    if regist_form.validate_on_submit(): # requeset.method == "POST" and form.validate()と同じ意味　　<-----------------会社登録ボタン
        new_company = Company(
            name=regist_form.name.data,
            industry=regist_form.industry.data,
            url=regist_form.url.data,
            user_id=current_user.id
        )
        db.session.add(new_company)
        db.session.commit()
        # REDIRECT
        return redirect(url_for('index', _anchor=('regist_new_company')))
    # GET
    return render_template('top_list.html', companies=companies, regist_form=regist_form, industries=industries)
### PRGパターン
### redirectがないと二重にPOSTされる可能性がある。
### redirectを書かなかったとき、フォームに入力後エンターキーを押したらDBに登録されたが表示はされなかった。
### そのあともう一度登録ボタンを押すと、二重にPOSTされる。

# 詳細ページ　表示
@app.route('/detail/<int:id>', methods=['GET', 'POST'])
@login_required
def show_detail(id):
    target = Company.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    info_form = DetailForm(obj=target, prefix="info") # DBに登録された情報をフォームの初期値とする
    schedule_form = ScheduleForm(prefix="schedule")
    # POST　詳細フォーム
    if info_form.toTopPage.data and info_form.validate_on_submit(): # <--      ヘッダー組み込みの保存して戻るボタン
        target.interest = info_form.interest.data
        target.memo = info_form.memo.data
        target.next_deadline = info_form.next_deadline.data
        db.session.commit()
        # REDIRECT
        return redirect(url_for('index'))
    if info_form.submit.data and info_form.validate_on_submit(): # <--      管理・メモの保存ボタン
        target.interest = info_form.interest.data
        target.memo = info_form.memo.data
        target.next_deadline = info_form.next_deadline.data
        db.session.commit()
        # REDIRECT
        return redirect(url_for('show_detail', id=id, _anchor=('detail-info-id')))
    # POST スケジュール
    if schedule_form.submit.data and schedule_form.validate_on_submit(): # <-- イベント登録ボタン
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
        return redirect(url_for('show_detail', id=id, _anchor=('add-event')))
    #GET
    return render_template('detail.html', company=target, info_form=info_form, schedule_form=schedule_form)

# 会社情報削除処理
@app.route('/delete_selected', methods=['POST'])
@login_required
def delete_company():
    ids = request.form.getlist('delete_targets')
    for delete_id in ids:
        target = Company.query.filter_by(id=delete_id, user_id=current_user.id).first()
        # 存在しない会社を削除しようとしてエラーになるのを防ぐ
        if target:
            db.session.delete(target)
    db.session.commit()
    return redirect(url_for('index'))

# イベント情報削除処理
@app.route('/schedule/delete/<int:id>', methods=['POST'])
@login_required
def delete_event(id):
    target = Schedule.query.filter_by(id=id).first()
    # イベントが存在し、かつ「そのイベントの会社」が自分のものである場合のみ削除
    if target and target.company.user_id == current_user.id:
        company_id = target.company_id
        db.session.delete(target)
        db.session.commit()
        return redirect(url_for('show_detail', id=company_id, _anchor='event-list'))
    return redirect(url_for('index'))

# 基本情報編集
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_company(id):
    target = Company.query.filter_by(id=id, user_id=current_user.id).first_or_404()
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

# イベント編集
@app.route('/schedule/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    target = Schedule.query.filter_by(id=id).first_or_404()
    # 権限チェック：そのイベントの親会社が自分のものでなければ 403 Forbidden
    if target.company.user_id != current_user.id:
        abort(403)
    schedule_form = ScheduleForm(obj=target) # DBに登録された情報をフォームの初期値とする
    event_company = Company.query.filter_by(id=target.company_id).first()
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
    return render_template('edit_schedule.html', schedule_form=schedule_form, event_company=event_company)


if __name__ == '__main__':
    app.run()
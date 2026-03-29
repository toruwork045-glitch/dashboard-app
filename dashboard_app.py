import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import io

st.set_page_config(page_title="仕入れ・販売差異分析ダッシュボード", layout="wide")

st.title("📊 仕入れ・販売差異分析ダッシュボード")

# サイドバーの設定
with st.sidebar:
    st.header("⚙️ 設定")
    data_source = st.radio(
        "データソースを選択:",
        ["サンプルデータを使用", "CSVをアップロード"]
    )

# データ読み込み関数
@st.cache_data
def load_sample_data():
    # サンプルデータパス
    purchase_path = '/sessions/clever-magical-franklin/mnt/outputs/野菜_仕入れ数量表.xlsx'
    sales_path = '/sessions/clever-magical-franklin/mnt/outputs/野菜_販売数量表.xlsx'

    df_purchase = pd.read_excel(purchase_path)
    df_sales = pd.read_excel(sales_path)

    return df_purchase, df_sales

# データ処理関数
def process_data(df_purchase, df_sales):
    # データの統合
    df_purchase = df_purchase.rename(columns={
        '仕入れ数量(kg)': '仕入れ数量',
        '仕入れ単価(円/kg)': '仕入れ単価',
        '仕入れ金額(円)': '仕入れ金額'
    })

    df_sales = df_sales.rename(columns={
        '販売数量(kg)': '販売数量',
        '販売単価(円/kg)': '販売単価',
        '販売金額(円)': '販売金額'
    })

    # マージ（品番・日付で統合）
    df_merged = df_purchase.merge(
        df_sales[['日付', '品番', '品名', '販売数量', '販売単価', '販売金額']],
        on=['日付', '品番', '品名'],
        how='outer'
    ).fillna(0)

    # 在庫計算
    df_merged['在庫量'] = df_merged['仕入れ数量'] - df_merged['販売数量']

    # 差異ステータス判定
    def judge_status(row):
        if row['販売数量'] == 0:
            return '未販売'
        elif row['在庫量'] > 0:
            return '在庫過剰'
        elif row['在庫量'] < 0:
            return '品切れ'
        else:
            return 'ちょうど'

    df_merged['ステータス'] = df_merged.apply(judge_status, axis=1)

    return df_merged

# データ読み込み
if data_source == "サンプルデータを使用":
    try:
        df_purchase, df_sales = load_sample_data()
        df_analysis = process_data(df_purchase, df_sales)
    except:
        st.error("サンプルデータの読み込みに失敗しました")
        st.stop()
else:
    col1, col2 = st.columns(2)
    with col1:
        purchase_file = st.file_uploader("仕入れデータ(CSV/Excel)", type=['csv', 'xlsx'])
    with col2:
        sales_file = st.file_uploader("販売データ(CSV/Excel)", type=['csv', 'xlsx'])

    if purchase_file and sales_file:
        df_purchase = pd.read_csv(purchase_file) if purchase_file.name.endswith('.csv') else pd.read_excel(purchase_file)
        df_sales = pd.read_csv(sales_file) if sales_file.name.endswith('.csv') else pd.read_excel(sales_file)
        df_analysis = process_data(df_purchase, df_sales)
    else:
        st.warning("両方のファイルをアップロードしてください")
        st.stop()

# === KPI サマリー ===
st.markdown("## 📈 KPI サマリー")
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_purchase_qty = df_analysis['仕入れ数量'].sum()
    st.metric("総仕入れ数量", f"{total_purchase_qty:.0f} kg")

with col2:
    total_sales_qty = df_analysis['販売数量'].sum()
    st.metric("総販売数量", f"{total_sales_qty:.0f} kg")

with col3:
    total_purchase_amt = df_analysis['仕入れ金額'].sum()
    st.metric("総仕入れ金額", f"¥{total_purchase_amt:,.0f}")

with col4:
    total_sales_amt = df_analysis['販売金額'].sum()
    st.metric("総販売金額", f"¥{total_sales_amt:,.0f}")

col1, col2, col3, col4 = st.columns(4)

with col1:
    inventory = df_analysis['在庫量'].sum()
    st.metric("現在の在庫量", f"{inventory:.0f} kg")

with col2:
    profit = total_sales_amt - total_purchase_amt
    st.metric("利益", f"¥{profit:,.0f}")

with col3:
    profit_margin = (profit / total_sales_amt * 100) if total_sales_amt > 0 else 0
    st.metric("利益率", f"{profit_margin:.1f}%")

with col4:
    unsold_items = len(df_analysis[df_analysis['ステータス'] == '未販売']['品名'].unique())
    st.metric("未販売品目数", f"{unsold_items} 種類")

# === グラフ可視化 ===
st.markdown("## 📊 グラフ分析")

# タブ分けて表示
tab1, tab2, tab3, tab4 = st.tabs(["仕入れ vs 販売", "品目別分析", "金額分析", "在庫状況"])

with tab1:
    col1, col2 = st.columns(2)

    with col1:
        # 品目別の仕入れ vs 販売
        by_item = df_analysis.groupby('品名')[['仕入れ数量', '販売数量']].sum().reset_index()

        fig = go.Figure(data=[
            go.Bar(name='仕入れ数量', x=by_item['品名'], y=by_item['仕入れ数量'], marker_color='#4472C4'),
            go.Bar(name='販売数量', x=by_item['品名'], y=by_item['販売数量'], marker_color='#70AD47')
        ])
        fig.update_layout(title="品目別：仕入れ vs 販売数量", barmode='group', height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # 日付別の推移
        by_date = df_analysis.groupby('日付')[['仕入れ数量', '販売数量']].sum().reset_index()

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=by_date['日付'], y=by_date['仕入れ数量'],
                                mode='lines+markers', name='仕入れ数量',
                                line=dict(color='#4472C4', width=2)))
        fig.add_trace(go.Scatter(x=by_date['日付'], y=by_date['販売数量'],
                                mode='lines+markers', name='販売数量',
                                line=dict(color='#70AD47', width=2)))
        fig.update_layout(title="日付別推移", height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    col1, col2 = st.columns(2)

    with col1:
        # ステータス分布
        status_count = df_analysis.groupby('ステータス').size()
        colors = {'在庫過剰': '#FF6B6B', '品切れ': '#FFA500', '未販売': '#87CEEB', 'ちょうど': '#90EE90'}

        fig = go.Figure(data=[
            go.Pie(labels=status_count.index, values=status_count.values,
                  marker=dict(colors=[colors.get(s, '#999') for s in status_count.index]))
        ])
        fig.update_layout(title="ステータス分布")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # 品目別の在庫量
        by_item_inventory = df_analysis.groupby('品名')['在庫量'].sum().reset_index().sort_values('在庫量')

        fig = go.Figure(data=[
            go.Bar(x=by_item_inventory['在庫量'], y=by_item_inventory['品名'],
                  orientation='h',
                  marker_color=['#FF6B6B' if x > 0 else '#90EE90' for x in by_item_inventory['在庫量']])
        ])
        fig.update_layout(title="品目別：在庫量", height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    col1, col2 = st.columns(2)

    with col1:
        # 品目別の仕入れ金額 vs 販売金額
        by_item_amt = df_analysis.groupby('品名')[['仕入れ金額', '販売金額']].sum().reset_index()

        fig = go.Figure(data=[
            go.Bar(name='仕入れ金額', x=by_item_amt['品名'], y=by_item_amt['仕入れ金額'], marker_color='#4472C4'),
            go.Bar(name='販売金額', x=by_item_amt['品名'], y=by_item_amt['販売金額'], marker_color='#70AD47')
        ])
        fig.update_layout(title="品目別：仕入れ金額 vs 販売金額", barmode='group', height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # 売上効率（販売数量 / 仕入れ数量）
        by_item_eff = df_analysis.groupby('品名')[['仕入れ数量', '販売数量']].sum().reset_index()
        by_item_eff['売上効率'] = (by_item_eff['販売数量'] / by_item_eff['仕入れ数量'] * 100).round(1)
        by_item_eff = by_item_eff.sort_values('売上効率')

        fig = go.Figure(data=[
            go.Bar(x=by_item_eff['売上効率'], y=by_item_eff['品名'],
                  orientation='h', marker_color='#FF6B6B')
        ])
        fig.update_layout(title="品目別：売上効率（%）", height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    # 在庫推移
    inventory_by_date = df_analysis.groupby('日付')['在庫量'].sum().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=inventory_by_date['日付'],
        y=inventory_by_date['在庫量'],
        fill='tozeroy',
        name='在庫量',
        line=dict(color='#4472C4', width=2)
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="ゼロ")
    fig.update_layout(title="在庫推移", height=400)
    st.plotly_chart(fig, use_container_width=True)

# === 詳細テーブル ===
st.markdown("## 📋 詳細テーブル")

# フィルター
col1, col2, col3 = st.columns(3)

with col1:
    selected_status = st.multiselect(
        "ステータスでフィルター:",
        options=df_analysis['ステータス'].unique(),
        default=df_analysis['ステータス'].unique()
    )

with col2:
    selected_items = st.multiselect(
        "品名でフィルター:",
        options=sorted(df_analysis['品名'].unique()),
        default=sorted(df_analysis['品名'].unique())
    )

with col3:
    sort_by = st.selectbox(
        "ソート:",
        options=['日付', '品名', '仕入れ数量', '販売数量', '在庫量', '仕入れ金額']
    )

# フィルタリング
df_filtered = df_analysis[
    (df_analysis['ステータス'].isin(selected_status)) &
    (df_analysis['品名'].isin(selected_items))
].sort_values(sort_by)

# 表示列の選択
display_cols = ['日付', '品番', '品名', '仕入れ数量', '販売数量', '在庫量',
                '仕入れ単価', '販売単価', '仕入れ金額', '販売金額', 'ステータス']

# テーブル表示
st.dataframe(
    df_filtered[display_cols].style.format({
        '仕入れ数量': '{:.0f}',
        '販売数量': '{:.0f}',
        '在庫量': '{:.0f}',
        '仕入れ単価': '¥{:,.0f}',
        '販売単価': '¥{:,.0f}',
        '仕入れ金額': '¥{:,.0f}',
        '販売金額': '¥{:,.0f}',
    }),
    use_container_width=True,
    height=400
)

# === エクスポート機能 ===
st.markdown("## 💾 エクスポート")
col1, col2 = st.columns(2)

with col1:
    csv_data = df_filtered[display_cols].to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 CSVダウンロード",
        data=csv_data,
        file_name=f"分析結果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

with col2:
    # Excelエクスポート
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_filtered[display_cols].to_excel(writer, sheet_name='分析結果', index=False)
    excel_buffer.seek(0)

    st.download_button(
        label="📥 Excelダウンロード",
        data=excel_buffer,
        file_name=f"分析結果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# フッター
st.markdown("---")
st.markdown("💡 **Tips**: サイドバーからデータソースを切り替えて、CSVをアップロードして分析することもできます。")

from flask import Flask, request, jsonify, redirect
import math
import sqlite3
import datetime

app = Flask(__name__)

# 数据库初始化
DATABASE = 'grid_trading.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # 创建网格计算结果表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grid_calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            stock_name TEXT NOT NULL,
            cost_price REAL,
            current_shares REAL,
            expected_profit REAL,
            current_price REAL,
            grid_count INTEGER,
            shares_per_grid REAL,
            price_increase_per_grid REAL,
            price_percentage_per_grid REAL,
            total_cost REAL,
            total_sold REAL,
            actual_profit REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 如果表已存在但缺少cost_price字段，则添加该字段
    try:
        cursor.execute('ALTER TABLE grid_calculations ADD COLUMN cost_price REAL')
        conn.commit()
    except sqlite3.OperationalError:
        # 字段已存在
        pass
    
    conn.commit()
    conn.close()

# 初始化数据库
init_db()

@app.route('/grid-trading/calculate_grid', methods=['POST'])
def calculate_grid():
    try:
        # 获取输入参数
        data = request.get_json()
        stock_code = data.get('stock_code', '')  # 默认空字符串
        stock_name = data.get('stock_name')
        cost_price = float(data.get('cost_price'))
        current_shares = float(data.get('current_shares'))
        expected_profit = float(data.get('expected_profit'))
        current_price = float(data.get('current_price'))
        grid_count = int(data.get('grid_count'))
        
        if grid_count <= 0:
            return jsonify({'error': '网格数量必须大于0'}), 400
            
        # 计算每网格股票数，四舍五入为100的整数倍
        shares_per_grid = current_shares / grid_count
        shares_per_grid = round(shares_per_grid / 100) * 100  # 四舍五入为100的整数倍
        
        # 计算每网格价格上涨（考虑卖出后剩余股票数量减少的情况）
        # 总盈利 = sum((剩余股票数量 * 价格上涨) for 每个网格)
        # 剩余股票数量变化：每次卖出shares_per_grid股
        # 第1次卖出：剩余股票数 = current_shares
        # 第2次卖出：剩余股票数 = current_shares - shares_per_grid
        # 第i次卖出：剩余股票数 = current_shares - (i-1)*shares_per_grid
        
        # 计算剩余股票数量的总和
        sum_of_remaining_shares = 0
        for i in range(grid_count):
            remaining_shares = current_shares - i * shares_per_grid
            sum_of_remaining_shares += remaining_shares
        
        # 计算每网格价格上涨，保留4位小数
        price_increase_per_grid = expected_profit / sum_of_remaining_shares
        price_increase_per_grid = round(price_increase_per_grid, 4)
        
        # 计算网格价格占比
        price_percentage_per_grid = (price_increase_per_grid / current_price) * 100
        price_percentage_per_grid = round(price_percentage_per_grid, 2)
        
        # 生成网格价格列表（包含上涨和下跌网格）
        grid_details = []
        grid_prices = []
        
        # 计算总卖出金额（用于参考）
        total_sold = 0
        total_bought = 0  # 新增：总买入金额
        remaining_shares = current_shares
        
        # 1. 生成下跌网格（固定3个）
        buy_grid_count = 3
        for i in range(1, buy_grid_count + 1):
            grid_price = current_price - i * price_increase_per_grid
            grid_price = round(grid_price, 4)
            
            # 添加到网格价格列表（保持价格从低到高排序）
            grid_prices.append(grid_price)
            
            # 计算买入股数（每下跌一个网格，买入每网格股票数）
            bought_shares = shares_per_grid
            
            # 计算买入金额
            bought_amount = bought_shares * grid_price
            total_bought += bought_amount
            
            # 更新剩余股票数量（买入后增加）
            remaining_shares += bought_shares
            
            grid_details.append({
                'price': grid_price,
                'type': 'buy',  # 新增：操作类型
                'shares': bought_shares,
                'amount': round(bought_amount, 2),
                'remaining_shares': remaining_shares
            })
        
        # 2. 重置剩余股数为当前股数（根据要求，上涨网格从当前股数开始计算）
        remaining_shares = current_shares
        
        # 3. 生成上涨网格（原有逻辑）
        for i in range(grid_count):
            grid_price = current_price + (i + 1) * price_increase_per_grid
            grid_price = round(grid_price, 4)
            
            # 添加到网格价格列表
            grid_prices.append(grid_price)
            
            # 计算实际卖出股数：如果剩余数大于每网格卖出股数，取网格卖出股数；否则取剩余数
            actual_sold_shares = min(remaining_shares, shares_per_grid)
            
            # 计算卖出金额
            sold_amount = actual_sold_shares * grid_price
            total_sold += sold_amount
            
            # 更新剩余股票数量
            remaining_shares -= actual_sold_shares
            
            grid_details.append({
                'price': grid_price,
                'type': 'sell',  # 新增：操作类型
                'shares': actual_sold_shares,
                'amount': round(sold_amount, 2),
                'remaining_shares': remaining_shares
            })
        
        # 按价格排序网格价格列表
        grid_prices.sort()
        
        # 计算实际总盈利（只计算从当前价格开始上升后经过各网格卖出后的总盈利）
        actual_profit = 0
        remaining_shares = current_shares
        
        # 处理上涨卖出网格，计算盈利（从当前股数开始，不考虑下跌买入）
        for i in range(grid_count):
            # 计算实际卖出股数
            actual_sold_shares = min(remaining_shares, shares_per_grid)
            # 计算当前网格的单网格盈利：(网格价格 - 当前价格) × 卖出股数
            # 网格价格 - 当前价格 = (i + 1) × price_increase_per_grid
            single_grid_profit = actual_sold_shares * (i + 1) * price_increase_per_grid
            actual_profit += single_grid_profit
            # 更新剩余股票数量
            remaining_shares -= actual_sold_shares
        
        actual_profit = round(actual_profit, 2)
        
        # 计算总成本（使用成本价）
        total_cost = current_shares * cost_price
        
        # 计算与成本价相关的指标
        current_value = current_shares * current_price  # 当前市值
        floating_profit = current_shares * (current_price - cost_price)  # 浮动盈亏
        floating_profit_ratio = (current_price - cost_price) / cost_price * 100 if cost_price > 0 else 0  # 浮动盈亏比例
        
        # 返回结果
        result = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'cost_price': cost_price,
            'current_shares': current_shares,
            'expected_profit': expected_profit,
            'current_price': current_price,
            'grid_count': grid_count,
            'shares_per_grid': shares_per_grid,
            'price_increase_per_grid': price_increase_per_grid,
            'price_percentage_per_grid': price_percentage_per_grid,
            'grid_prices': grid_prices,
            'grid_details': grid_details,
            'total_cost': round(total_cost, 2),
            'current_value': round(current_value, 2),
            'floating_profit': round(floating_profit, 2),
            'floating_profit_ratio': round(floating_profit_ratio, 2),
            'total_sold': round(total_sold, 2),
            'total_bought': round(total_bought, 2),  # 新增：总买入金额
            'actual_profit': actual_profit
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/grid-trading/save_calculation', methods=['POST'])
def save_calculation():
    try:
        data = request.get_json()
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # 检查是否已存在相同股票名称的记录
        cursor.execute('''
            SELECT id FROM grid_calculations WHERE stock_name = ?
        ''', (data['stock_name'],))
        existing_record = cursor.fetchone()
        
        if existing_record:
            # 更新现有记录
            cursor.execute('''
                UPDATE grid_calculations SET 
                    stock_code = ?, 
                    cost_price = ?, 
                    current_shares = ?, 
                    expected_profit = ?, 
                    current_price = ?, 
                    grid_count = ?, 
                    shares_per_grid = ?, 
                    price_increase_per_grid = ?, 
                    price_percentage_per_grid = ?, 
                    total_cost = ?, 
                    total_sold = ?, 
                    actual_profit = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE stock_name = ?
            ''', (
                data.get('stock_code'),
                data['cost_price'],
                data['current_shares'],
                data['expected_profit'],
                data['current_price'],
                data['grid_count'],
                data['shares_per_grid'],
                data['price_increase_per_grid'],
                data['price_percentage_per_grid'],
                data['total_cost'],
                data['total_sold'],
                data['actual_profit'],
                data['stock_name']
            ))
            calculation_id = existing_record[0]
            action = 'updated'
        else:
            # 插入新记录
            cursor.execute('''
                INSERT INTO grid_calculations (
                    stock_code, stock_name, cost_price, current_shares, expected_profit, current_price, 
                    grid_count, shares_per_grid, price_increase_per_grid, price_percentage_per_grid, 
                    total_cost, total_sold, actual_profit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('stock_code'),
                data['stock_name'],
                data['cost_price'],
                data['current_shares'],
                data['expected_profit'],
                data['current_price'],
                data['grid_count'],
                data['shares_per_grid'],
                data['price_increase_per_grid'],
                data['price_percentage_per_grid'],
                data['total_cost'],
                data['total_sold'],
                data['actual_profit']
            ))
            calculation_id = cursor.lastrowid
            action = 'created'
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'action': action,
            'calculation_id': calculation_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/grid-trading/get_history', methods=['GET'])
def get_history():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # 查询所有记录，按更新时间倒序
        cursor.execute('''
            SELECT id, stock_code, stock_name, cost_price, current_shares, expected_profit, current_price, 
                   grid_count, actual_profit, created_at, updated_at
            FROM grid_calculations
            ORDER BY updated_at DESC
        ''')
        
        records = cursor.fetchall()
        conn.close()
        
        # 格式化结果
        history = []
        for record in records:
            history.append({
                'id': record[0],
                'stock_code': record[1],
                'stock_name': record[2],
                'cost_price': record[3],
                'current_shares': record[4],
                'expected_profit': record[5],
                'current_price': record[6],
                'grid_count': record[7],
                'actual_profit': record[8],
                'created_at': record[9],
                'updated_at': record[10]
            })
        
        return jsonify({'history': history})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/grid-trading/get_calculation/<int:id>', methods=['GET'])
def get_calculation(id):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # 查询指定ID的记录
        cursor.execute('''
            SELECT id, stock_code, stock_name, cost_price, current_shares, expected_profit, current_price, 
                   grid_count, shares_per_grid, price_increase_per_grid, price_percentage_per_grid,
                   total_cost, total_sold, actual_profit
            FROM grid_calculations
            WHERE id = ?
        ''', (id,))
        
        record = cursor.fetchone()
        conn.close()
        
        if not record:
            return jsonify({'error': '记录不存在'}), 404
        
        # 格式化结果
        calculation = {
            'id': record[0],
            'stock_code': record[1],
            'stock_name': record[2],
            'cost_price': record[3],
            'current_shares': record[4],
            'expected_profit': record[5],
            'current_price': record[6],
            'grid_count': record[7],
            'shares_per_grid': record[8],
            'price_increase_per_grid': record[9],
            'price_percentage_per_grid': record[10],
            'total_cost': record[11],
            'total_sold': record[12],
            'actual_profit': record[13],
            # 添加网格价格列表和网格详情
            'grid_prices': [],
            'grid_details': []
        }
        
        # 生成网格价格列表和网格详情（包含下跌和上涨网格）
        grid_prices = []
        grid_details = []
        remaining_shares = calculation['current_shares']
        
        # 1. 生成下跌网格（固定3个）
        buy_grid_count = 3
        for i in range(1, buy_grid_count + 1):
            grid_price = calculation['current_price'] - i * calculation['price_increase_per_grid']
            grid_price = round(grid_price, 4)
            
            # 计算买入股数（每下跌一个网格，买入每网格股票数）
            bought_shares = calculation['shares_per_grid']
            
            # 计算买入金额
            bought_amount = bought_shares * grid_price
            
            # 更新剩余股票数量（买入后增加）
            remaining_shares += bought_shares
            
            grid_prices.append(grid_price)
            grid_details.append({
                'price': grid_price,
                'type': 'buy',
                'shares': bought_shares,
                'amount': round(bought_amount, 2),
                'remaining_shares': remaining_shares
            })
        
        # 2. 重置剩余股数为当前股数（根据要求，上涨网格从当前股数开始计算）
        remaining_shares = calculation['current_shares']
        
        # 3. 生成上涨网格
        for i in range(calculation['grid_count']):
            grid_price = calculation['current_price'] + (i + 1) * calculation['price_increase_per_grid']
            grid_price = round(grid_price, 4)
            
            # 计算实际卖出股数：如果剩余数大于每网格卖出股数，取网格卖出股数；否则取剩余数
            actual_sold_shares = min(remaining_shares, calculation['shares_per_grid'])
            
            # 计算卖出金额
            sold_amount = actual_sold_shares * grid_price
            
            # 计算当前网格卖出盈利 = 实际卖出股数 * 网格价格间距
            grid_sold_profit = actual_sold_shares * calculation['price_increase_per_grid']
            grid_sold_profit = round(grid_sold_profit, 2)
            
            # 更新剩余股票数量
            remaining_shares -= actual_sold_shares
            
            grid_prices.append(grid_price)
            grid_details.append({
                'price': grid_price,
                'type': 'sell',
                'shares': actual_sold_shares,
                'amount': round(sold_amount, 2),
                'remaining_shares': remaining_shares,
                'sold_profit': grid_sold_profit
            })
        
        # 按价格排序网格价格列表
        grid_prices.sort()
        
        calculation['grid_prices'] = grid_prices
        calculation['grid_details'] = grid_details
        
        return jsonify({'calculation': calculation})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/grid-trading/delete_calculation/<int:id>', methods=['DELETE'])
def delete_calculation(id):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Check if record exists
        cursor.execute('SELECT id FROM grid_calculations WHERE id = ?', (id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': '记录不存在'}), 404
        
        # Delete record
        cursor.execute('DELETE FROM grid_calculations WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': '记录已删除'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/')
def root():
    # 根路径重定向到带上下文的路径
    return redirect('/grid-trading/')

@app.route('/grid-trading/')
def index():
    # 返回HTML页面
    return open('grid_trading.html', 'r', encoding='utf-8').read()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5008)
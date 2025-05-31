# res://tests/run_100yrs.gd
extends SceneTree          # ← ここを Node から SceneTree に変更

func _init():             # _ready() ではなく最初に呼ばれる _init() を使う
	# WorldSim インスタンス化
	var sim = WorldSim.new()
	# 100 年分のシミュレーション
	sim.simulate_years(100)
	# 完了ログ
	print("✅ 100-year sim completed")
	# 終了コード 0 でプロセスを抜ける
	quit(0)

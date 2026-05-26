/**
 * SwitchBot Monitor - インデックスページのチャートロジック
 * 
 * このファイルはメインダッシュボードのサマリーチャートの描画を処理します。
 * 各チャートは特定のデバイスの24時間の温度と湿度の履歴を表示します。
 * 
 * Copyright 20260526a Hiroaki GOTO as GORRY
 */

function initIndexCharts(historyData) {
    /**
     * historyData内の各デバイスを反復処理し、それぞれのチャートを作成します。
     * historyDataはデバイスIDをキーとするオブジェクトです。
     */
    Object.keys(historyData).forEach(deviceId => {
        // 現在のデバイスのcanvas要素を取得
        const canvas = document.getElementById(`chart-${deviceId}`);
        if (!canvas) return; // 要素が見つからない場合はスキップ
        
        const ctx = canvas.getContext('2d');
        const data = historyData[deviceId];
        
        // X軸のための固定の24時間範囲を定義
        const start = new Date(data.start);
        const end = new Date(data.end);
        
        // 生のポイントデータをChart.jsの座標フォーマット {x, y} に変換
        const tempPoints = data.points.map(p => ({ x: new Date(p.x), y: p.y_temp }));
        const humiPoints = data.points.map(p => ({ x: new Date(p.x), y: p.y_humi }));

        // スケーリングのための最小値/最大値を計算するために温度と湿度の値を抽出
        const temps = data.points.map(p => p.y_temp);
        const humis = data.points.map(p => p.y_humi);
        const maxTemp = temps.length ? Math.max(...temps) : null;
        const minTemp = temps.length ? Math.min(...temps) : null;
        const maxHumi = humis.length ? Math.max(...humis) : null;
        const minHumi = humis.length ? Math.min(...humis) : null;

        /**
         * 線がチャートの上部または下部に直接くっつくのを防ぐために、
         * Y軸の余白（マージン）を計算します。
         */
        const tempMargin = (maxTemp - minTemp) * 0.15 || 1;
        const humiMargin = (maxHumi - minHumi) * 0.15 || 5;

        // Chart.jsインスタンスを初期化
        new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: '温度', // 温度データセット
                        data: tempPoints,
                        borderColor: '#ff5722',
                        backgroundColor: '#ff572233',
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.3,
                        yAxisID: 'y-temp',
                    },
                    {
                        label: '湿度', // 湿度データセット
                        data: humiPoints,
                        borderColor: '#2196f3',
                        backgroundColor: '#2196f333',
                        borderWidth: 1,
                        pointRadius: 0,
                        tension: 0.3,
                        yAxisID: 'y-humi',
                        borderDash: [5, 5] // 湿度は破線で表示
                    }
                ]
            },
            plugins: [{
                /**
                 * 最大値と最小値のラベルをチャートキャンバス上に直接描画する
                 * カスタムプラグイン。
                 */
                id: 'extremaLabels',
                afterDraw: (chart) => {
                    const { ctx, chartArea: { top, bottom, left, right } } = chart;
                    ctx.save();
                    ctx.font = 'bold 10px sans-serif';
                    
                    // 左端に湿度の最大値/最小値を描画
                    if (maxHumi !== null) {
                        ctx.fillStyle = '#2196f3';
                        ctx.textAlign = 'left';
                        ctx.textBaseline = 'top';
                        ctx.fillText(`${maxHumi}%`, left, top);
                        ctx.textBaseline = 'bottom';
                        ctx.fillText(`${minHumi}%`, left, bottom);
                    }

                    // 右端に温度の最大値/最小値を描画
                    if (maxTemp !== null) {
                        ctx.fillStyle = '#ff5722';
                        ctx.textAlign = 'right';
                        ctx.textBaseline = 'top';
                        ctx.fillText(`${maxTemp.toFixed(1)}℃`, right, top);
                        ctx.textBaseline = 'bottom';
                        ctx.fillText(`${minTemp.toFixed(1)}℃`, right, bottom);
                    }
                    ctx.restore();
                }
            }],
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 0, bottom: 0 } },
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                const d = new Date(context[0].raw.x);
                                return d.getFullYear() + '/' + 
                                       String(d.getMonth() + 1).padStart(2, '0') + '/' + 
                                       String(d.getDate()).padStart(2, '0') + ' ' + 
                                       String(d.getHours()).padStart(2, '0') + ':' + 
                                       String(d.getMinutes()).padStart(2, '0');
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        /**
                         * 時間ベースの水平軸。
                         * カスタムの目盛り生成を使用して、0、6、12、18時のみラベルを表示します。
                         */
                        type: 'linear',
                        min: start.getTime(),
                        max: end.getTime(),
                        afterBuildTicks: (axis) => {
                            const ticks = [];
                            let t = new Date(start);
                            t.setMinutes(0, 0, 0); 
                            // 最初の目盛りが開始時刻以降になるようにする
                            if (t < start) t.setHours(t.getHours() + 1);
                            // 1時間ごとに目盛りを生成
                            while (t <= end) {
                                ticks.push({ value: t.getTime() });
                                t.setHours(t.getHours() + 1);
                            }
                            axis.ticks = ticks;
                        },
                        ticks: {
                            font: { size: 10 },
                            color: '#888',
                            autoSkip: false,
                            callback: function(value) {
                                const date = new Date(value);
                                const h = date.getHours();
                                // 0時の場合は日付(MM/DD)を表示、それ以外（6, 12, 18）は時刻を表示
                                if (h === 0) {
                                    return (date.getMonth() + 1) + '/' + date.getDate();
                                }
                                return [6, 12, 18].includes(h) ? String(h) : '';
                            }
                        },
                        grid: {
                            display: true,
                            drawBorder: false,
                            drawTicks: false,
                            color: (context) => {
                                const date = new Date(context.tick.value);
                                const h = date.getHours();
                                // 主要な時間間隔でのみグリッド線を描画
                                if ([0, 6, 12, 18].includes(h)) {
                                    return 'rgba(0, 0, 0, 0.3)';
                                }
                                return 'rgba(0, 0, 0, 0.15)';
                                // return 'transparent';
                            },
                            borderDash: [5, 5]
                        },
                        border: { display: true }
                    },
                    'y-temp': {
                        /**
                         * 温度スケーリングのための非表示のY軸。
                         */
                        display: false,
                        position: 'left',
                        min: minTemp - tempMargin,
                        max: maxTemp + tempMargin,
                        border: { display: false }
                    },
                    'y-humi': {
                        /**
                         * 湿度スケーリングのための非表示のY軸。
                         */
                        display: false,
                        position: 'right',
                        min: Math.max(0, minHumi - humiMargin),
                        max: Math.min(100, maxHumi + humiMargin),
                        border: { display: false }
                    }
                }
            }
        });
    });

    /**
     * 5分ごと（300,000ミリ秒）にページを自動的にリロードするタイマーを設定します。
     * これにより、ダッシュボードのデータが最新に保たれます。
     */
    setTimeout(() => location.reload(), 300000);
}

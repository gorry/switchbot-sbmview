/**
 * SwitchBot Monitor - 詳細ページのチャートおよびコントロールロジック
 * 
 * このファイルは、デバイス詳細ページにおけるナビゲーション、スケール切り替え、
 * および複雑なチャートの描画を処理します。
 * 
 * Copyright 20260526a Hiroaki GOTO as GORRY
 */

function initDetailCharts(params) {
    const { scale, currentDate, minDate, maxDate, cardsData, orderIndex, typeId } = params;

    /**
     * 現在のスケールに基づいてタイムラインを前後に移動します。
     * @param {number} dir - 方向: -1 (前へ)、1 (次へ)。
     */
    window.moveDate = function(dir) {
        let d = new Date(currentDate.slice(0,4), currentDate.slice(4,6)-1, currentDate.slice(6,8));
        
        // 現在の表示スケールに基づいて新しい日付を計算
        if (scale === 1) d.setDate(d.getDate() + dir);
        else if (scale === 2) d.setDate(d.getDate() + (dir * 3));
        else if (scale === 3) d.setDate(d.getDate() + (dir * 7));
        else if (scale === 4) d.setMonth(d.getMonth() + dir);
        else if (scale === 5) d.setMonth(d.getMonth() + (dir * 3));
        else if (scale === 6) d.setFullYear(d.getFullYear() + dir);
        
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        jumpDate(`${yyyy}${mm}${dd}`);
    }

    /**
     * 特定の日付の詳細ページにリダイレクトします。
     * @param {string} val - 日付文字列 (YYYY-MM-DD または YYYYMMDD)。
     */
    window.jumpDate = function(val) {
        const dateStr = val.replace(/-/g, '');
        location.href = `/detail?device=${orderIndex}&scale=${scale}&type=${typeId}&date=${dateStr}`;
    }

    /**
     * 表示スケール (1日、3日、1週間、1ヶ月、3ヶ月、1年) を変更します。
     * @param {number} newScale - 切り替えるスケールID。
     */
    window.changeScale = function(newScale) {
        location.href = `/detail?device=${orderIndex}&scale=${newScale}&type=${typeId}&date=${currentDate}`;
    }

    /**
     * 比較タイプ (なし、前期と比較、前年と比較) を変更します。
     * @param {number} newType - 比較タイプID。
     */
    window.changeType = function(newType) {
        location.href = `/detail?device=${orderIndex}&scale=${scale}&type=${newType}&date=${currentDate}`;
    }

    /**
     * 現在の日付がデータベース内の利用可能なデータの境界に達した場合、
     * ナビゲーションボタンを無効にします。
     */
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    if (prevBtn) prevBtn.disabled = (currentDate <= minDate);
    if (nextBtn) nextBtn.disabled = (currentDate >= maxDate);

    /**
     * 1つまたは複数のカード (現在および比較カード) をレンダリングします。
     */
    cardsData.forEach((card, index) => {
        const chartElement = document.getElementById(`chart-${index + 1}`);
        if (!chartElement) return;
        
        const ctx = chartElement.getContext('2d');
        const start = new Date(card.start);
        const end = new Date(card.end);

        const datasets = [];
        
        /**
         * 短期スケール (1日から1週間) の場合、生のセンサーデータポイントをプロットします。
         */
        if (scale <= 3) {
            // 温度線（実測値）
            let tempDataset = {
                label: '気温',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_temp })),
                borderColor: '#ff5722',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.1,
                yAxisID: 'y-temp'
            };

            // 期間平均が存在する場合、期間平均を基準に背景領域を塗り分ける
            if (card.avg_temp !== null) {
                tempDataset.fill = {
                    target: { value: card.avg_temp },
                    above: 'rgba(255, 87, 34, 0.2)', // 平均より上は薄い赤
                    below: 'rgba(33, 150, 243, 0.2)' // 平均より下は薄い青
                };
            }
            datasets.push(tempDataset);

            // 期間平均気温線（期間全体の平均値を水平線として表示）
            if (card.avg_temp !== null) {
                datasets.push({
                    label: '期間平均気温',
                    data: [
                        { x: start, y: card.avg_temp },
                        { x: end, y: card.avg_temp }
                    ],
                    borderColor: '#888',
                    borderWidth: 1,
                    borderDash: [2, 2], // 細い点線
                    pointRadius: 0,
                    yAxisID: 'y-temp'
                });
            }

            // 湿度破線
            datasets.push({
                label: '湿度',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_humi })),
                borderColor: '#2196f3',
                borderWidth: 1,
                borderDash: [5, 5],
                pointRadius: 0,
                tension: 0.1,
                yAxisID: 'y-humi'
            });
            // バッテリー残量ステータス線
            datasets.push({
                label: 'バッテリー',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_batt })),
                borderColor: '#4caf50',
                borderWidth: 2,
                borderDash: [2, 2],
                pointRadius: 0,
                tension: 0,
                yAxisID: 'y-humi' 
            });
        } 
        /**
         * 長期スケール (1ヶ月から1年) の場合、集計された日次平均、
         * 最大値、および最小値をプロットします。
         */
        else {
            // 最高気温 (塗りつぶし領域の上部)
            datasets.push({
                label: '最高気温',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_max })),
                borderColor: '#ff5722',
                borderWidth: 2,
                pointRadius: 0,
                fill: '+1',
                backgroundColor: 'rgba(255, 87, 34, 0.2)',
                yAxisID: 'y-temp'
            });
            // 日次平均気温線
            datasets.push({
                label: '日次平均気温',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_avg })),
                borderColor: '#888',
                borderWidth: 1,
                borderDash: [2, 2], // 細い点線
                pointRadius: 0,
                yAxisID: 'y-temp'
            });
            // 最低気温 (塗りつぶし領域の下部)
            datasets.push({
                label: '最低気温',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_min })),
                borderColor: '#2196f3',
                borderWidth: 2,
                pointRadius: 0,
                fill: '-1',
                backgroundColor: 'rgba(33, 150, 243, 0.2)',
                yAxisID: 'y-temp'
            });

            // 期間平均気温線（期間全体の平均値を水平線として表示）
            if (card.avg_temp !== null) {
                datasets.push({
                    label: '期間平均気温',
                    data: [
                        { x: start, y: card.avg_temp },
                        { x: end, y: card.avg_temp }
                    ],
                    borderColor: '#888',
                    borderWidth: 1,
                    borderDash: [2, 2], // 細い点線
                    pointRadius: 0,
                    yAxisID: 'y-temp'
                });
            }

            // 日次平均湿度
            datasets.push({
                label: '平均湿度',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_humi })),
                borderColor: '#2196f3',
                borderWidth: 1,
                borderDash: [5, 5],
                pointRadius: 0,
                yAxisID: 'y-humi'
            });
            // 各日の開始時点のバッテリー残量
            datasets.push({
                label: 'バッテリー',
                data: card.points.map(p => ({ x: new Date(p.x), y: p.y_batt })),
                borderColor: '#4caf50',
                borderWidth: 2,
                borderDash: [2, 2],
                pointRadius: 0,
                tension: 0,
                yAxisID: 'y-humi'
            });
        }

        // サマリーテキストを描画するために、現在のビューの絶対最大/最小値を計算
        const temps = card.points.map(p => scale <= 3 ? p.y_temp : p.y_max).filter(v => v !== null);
        const humis = card.points.map(p => p.y_humi).filter(v => v !== null);
        const absMaxTemp = temps.length ? Math.max(...temps) : null;
        const absMinTemp = card.points.map(p => scale <= 3 ? p.y_temp : p.y_min).filter(v => v !== null);
        const absMinT = absMinTemp.length ? Math.min(...absMinTemp) : null;
        const absMaxHumi = humis.length ? Math.max(...humis) : null;
        const absMinHumi = humis.length ? Math.min(...humis) : null;

        new Chart(ctx, {
            type: 'line',
            data: { datasets },
            plugins: [{
                /**
                 * チャート領域に数値の最大/最小インジケーターをレンダリングするプラグイン。
                 */
                id: 'extremaLabels',
                afterDraw: (chart) => {
                    const { ctx, chartArea: { top, bottom, left, right }, scales: { 'y-temp': yTempScale } } = chart;
                    ctx.save();
                    ctx.font = 'bold 10px sans-serif';
                    
                    // 右側: 温度の最大 (上部) と最小 (下部)
                    if (absMaxTemp !== null) {
                        ctx.fillStyle = '#ff5722';
                        ctx.textAlign = 'right';
                        ctx.textBaseline = 'top';
                        ctx.fillText(`${absMaxTemp.toFixed(1)}℃`, right - 5, top + 5);
                        ctx.textBaseline = 'bottom';
                        ctx.fillText(`${absMinT.toFixed(1)}℃`, right - 5, bottom - 5);
                    }

                    // 期間平均気温のラベル描画 (右端)
                    if (card.avg_temp !== null) {
                        const yPos = yTempScale.getPixelForValue(card.avg_temp);
                        const label = `${card.avg_temp.toFixed(1)}℃`;
                        const textWidth = ctx.measureText(label).width;
                        const padding = 2;
                        
                        // ラベル背景の白ボックスを描画 (重なっても見やすくするため)
                        ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
                        ctx.strokeStyle = '#888';
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.rect(right - textWidth - padding * 2 - 5, yPos - 6, textWidth + padding * 2, 12);
                        ctx.fill();
                        ctx.stroke();

                        // ラベルテキストを描画
                        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
                        ctx.textAlign = 'right';
                        ctx.textBaseline = 'middle';
                        ctx.fillText(label, right - 5 - padding, yPos);
                    }

                    // 左側: 湿度の最大 (上部) と最小 (下部)
                    if (absMaxHumi !== null) {
                        ctx.fillStyle = '#2196f3';
                        ctx.textAlign = 'left';
                        ctx.textBaseline = 'top';
                        ctx.fillText(`${absMaxHumi}%`, left + 5, top + 5);
                        ctx.textBaseline = 'bottom';
                        ctx.fillText(`${absMinHumi}%`, left + 5, bottom - 5);
                    }
                    ctx.restore();
                }
            }],
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false, // 応答を速くするためにアニメーションを無効化
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                const d = new Date(context[0].raw.x);
                                let label = d.getFullYear() + '/' + 
                                            String(d.getMonth() + 1).padStart(2, '0') + '/' + 
                                            String(d.getDate()).padStart(2, '0');
                                if (scale <= 3) {
                                    label += ' ' + String(d.getHours()).padStart(2, '0') + ':' + 
                                             String(d.getMinutes()).padStart(2, '0');
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        min: start.getTime(),
                        max: end.getTime(),
                        /**
                         * 現在のスケールに基づいて、目盛りとグリッド線が
                         * 表示される位置を決定するロジック。
                         */
                        afterBuildTicks: (axis) => {
                            const ticks = [];
                            let t = new Date(start);
                            if (scale === 1) { // 1日: 1時間ごとに目盛り
                                t.setHours(0,0,0,0);
                                for(let i=0; i<=24; i+=1) {
                                    ticks.push({ value: new Date(t).setHours(i) });
                                }
                            } else if (scale === 2 || scale === 3) { // 3日 / 1週間: 2時間または6時間ごとに目盛り
                                t.setHours(0,0,0,0);
                                const step = scale === 2 ? 2 : 6;
                                while(t <= end) {
                                    ticks.push({ value: t.getTime() });
                                    t.setHours(t.getHours() + step);
                                }
                            } else if (scale === 4) { // 1ヶ月: 毎日目盛り、1/6/11/16/21/26日と翌月1日にラベル
                                t.setHours(0,0,0,0);
                                while(t <= end) {
                                    ticks.push({ value: t.getTime() });
                                    t.setDate(t.getDate() + 1);
                                }
                            } else if (scale === 5) { // 3ヶ月: 1/6/11/16/21/26日と翌月1日に目盛り
                                t.setHours(0,0,0,0);
                                while(t <= end) {
                                    ticks.push({ value: t.getTime() });
                                    t.setDate(t.getDate() + 1);
                                }
                            } else if (scale === 6) { // 1年: 各月の1日と翌年1/1に目盛り
                                t.setMonth(0, 1); t.setHours(0,0,0,0);
                                while(t <= end) {
                                    ticks.push({ value: t.getTime() });
                                    t.setDate(t.getDate() + 1);
                                }
                            }
                            axis.ticks = ticks;
                        },
                        ticks: {
                            autoSkip: false,
                            /**
                             * 各目盛りに表示されるラベルをフォーマットします。
                             */
                            callback: function(value) {
                                const d = new Date(value);
                                const h = d.getHours();
                                const date = d.getDate();
                                const m = d.getMonth() + 1;
                                const y = d.getYear() + 1900;
                                if (scale === 1) {
                                    if (h === 0) return (m + "/" + date);
                                    if (h === 6 || h === 12 || h === 18) return h;
                                }
                                if (scale === 2) {
                                    if (h === 0) return (m + "/" + date);
                                    if (h === 6 || h === 12 || h === 18) return h;
                                }
                                if (scale === 3) {
                                    if (h === 0) {
                                        return m + "/" + date;
                                    }
                                }
                                if (scale === 4) {
                                    if (date === 1) return m + "/" + date;
                                    if (date === 6 || date === 11 || date === 16 || date === 21 || date === 26 || +d == +end) return m + "/" + date;
                                }
                                if (scale === 5) {
                                    if (date === 1) return m + "/" + date;
                                    if (date === 6 || date === 11 || date === 16 || date === 21 || date === 26 || +d === +end) return date;
                                }
                                if (scale === 6) {
                                    if (date === 1) {
                                        if (m === 1) return (y + "/" + m);
                                        return m;
                                    }
                                }
                                return '';
                            },
                            font: { size: 9 }
                        },
                        grid: {
                            /**
                             * 垂直グリッド線の表示と色を制御します。
                             */
                            color: (c) => {
                                const value = c.tick.value;
                                const d = new Date(value);
                                const h = d.getHours();
                                const date = d.getDate();
                                const m = d.getMonth() + 1;
                                if (scale === 1) {
                                    if (h === 0 || h === 6 || h === 12 || h === 18) return 'rgba(0,0,0,0.3)';
                                    return 'rgba(0,0,0,0.1)';
                                }
                                if (scale === 2) {
                                    if (h === 0) return 'rgba(0,0,0,0.3)';
                                    return 'rgba(0,0,0,0.1)';
                                }
                                if (scale === 3) {
                                    if (h === 0) return 'rgba(0,0,0,0.3)';
                                    return 'rgba(0,0,0,0.1)';
                                }
                                if (scale === 4) {
                                    if (date === 1 || date === 6 || date === 11 || date === 16 || date === 21 || date === 26 || +d === +end) return 'rgba(0,0,0,0.3)';
                                    return 'rgba(0,0,0,0.15)';
                                }
                                if (scale === 5) {
                                    if (date === 1 || +d === +end) return 'rgba(0,0,0,0.3)';
                                    if (date === 6 || date === 11 || date === 16 || date === 21 || date === 26) return 'rgba(0,0,0,0.15)';
                                }
                                if (scale === 6) {
                                    if (date === 1 || +d === +end) return 'rgba(0,0,0,0.3)';
                                }
                                return 'transparent';
                            },
                            borderDash: [2, 2]
                        }
                    },
                    'y-temp': {
                        position: 'right',
                        min: -20, max: 40,
                        ticks: {
                            stepSize: 10,
                            font: { size: 10 },
                            color: '#ff5722',
                            callback: (v) => v + '℃'
                        },
                        grid: {
                            // 0度線を強調表示
                            color: (c) => c.tick.value === 0 ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.1)',
                            lineWidth: (c) => c.tick.value === 0 ? 2 : 1
                        }
                    },
                    'y-humi': {
                        position: 'left',
                        min: -50, max: 100, // 0-100%を温度範囲に合わせるためのオフセット
                        ticks: {
                            stepSize: 25,
                            font: { size: 10 },
                            color: '#2196f3',
                            callback: (v) => v >= 0 ? v + '%' : ''
                        },
                        grid: { display: false }
                    }
                }
            }
        });
    });
}

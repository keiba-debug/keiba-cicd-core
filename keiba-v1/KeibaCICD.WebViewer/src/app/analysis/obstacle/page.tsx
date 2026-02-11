"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Target, Star, Activity, MapPin, BarChart3, Zap, Eye, Mountain, Gauge, Route, Info } from "lucide-react"

const obstacleLevelData: Record<string, Record<string, number>> = {
  京都: {
    "3930芝": 53,
    "3170芝": 44,
    "3170ダ": 43,
    "2910ダ": 36,
  },
  阪神: {
    "3900芝": 40,
    "3140芝": 34,
    "3110ダ": 34,
    "2970ダ": 33,
  },
  中山: {
    "4250芝": 37,
    "4100芝": 35,
    "3570芝": 34,
    "3560芝": 33,
    "3200ダ": 31,
    "3210芝": 31,
    "2880ダ": 21,
  },
  東京: {
    "3110芝": 29,
    "3000ダ": 28,
    "3100ダ": 28,
  },
  小倉: {
    "3390芝": 27,
    "2860芝": 24,
  },
  中京: {
    "3300芝": 25,
    "3330芝": 25,
    "3000芝": 23,
  },
  新潟: {
    "3250芝": 22,
    "3290芝": 22,
    "2850芝": 18,
    "2890芝": 18,
  },
  福島: {
    "3350芝": 19,
    "3380芝": 19,
    "2750芝": 15,
    "2770芝": 15,
  },
}

const racetrackData: Record<
  string,
  {
    name: string
    location: string
    features: string[]
    obstacleFeatures: string[]
    difficulty: string
    url: string
  }
> = {
  東京: {
    name: "東京競馬場",
    location: "府中市",
    features: ["直線525m", "高低差2.7m", "右回り"],
    obstacleFeatures: ["大型竹柵", "生垣障害", "水濠"],
    difficulty: "中級",
    url: "https://www.jra.go.jp/facilities/race/tokyo/course/",
  },
  中山: {
    name: "中山競馬場",
    location: "船橋市",
    features: ["直線310m", "高低差1.6m", "右回り"],
    obstacleFeatures: ["小障害中心", "技術重視", "急坂あり"],
    difficulty: "上級",
    url: "https://www.jra.go.jp/facilities/race/nakayama/course/",
  },
  京都: {
    name: "京都競馬場",
    location: "京都市",
    features: ["直線404m", "平坦", "右回り"],
    obstacleFeatures: ["最高難度", "大型障害", "技術・スタミナ必須"],
    difficulty: "最上級",
    url: "https://www.jra.go.jp/facilities/race/kyoto/course/",
  },
  阪神: {
    name: "阪神競馬場",
    location: "宝塚市",
    features: ["直線356m", "高低差4.3m", "右回り"],
    obstacleFeatures: ["起伏激しい", "坂路障害", "体力消耗大"],
    difficulty: "上級",
    url: "https://www.jra.go.jp/facilities/race/hanshin/course/",
  },
}

type Horse = {
  id: number
  name: string
  jockey: string
  obstacleRaces: number
  obstacleWins: number
  jumpQuality: number
  aptitudeScore: number
  venueRecord: Record<string, string>
  levelExperience: Record<string, number>
  flatRecord: Record<string, number>
  courseSpecialty: number
  odds: number
}

const mockRaceData: { raceInfo: Record<string, string | number>; horses: Horse[] } = {
  raceInfo: {
    name: "第158回 中山大障害",
    venue: "中山",
    distance: "4100m",
    surface: "芝",
    obstacleLevel: 35,
    obstacles: 16,
    weather: "晴",
    track: "良",
    date: "2024-12-28",
  },
  horses: [
    {
      id: 1,
      name: "サンライズホープ",
      jockey: "森一馬",
      obstacleRaces: 8,
      obstacleWins: 3,
      jumpQuality: 4.2,
      aptitudeScore: 85,
      venueRecord: { 中山: "2-1-1-2", 東京: "1-0-1-1" },
      levelExperience: { "30-39": 5, "20-29": 3 },
      flatRecord: { turfMile: 78, dirt1800: 82 },
      courseSpecialty: 0.8,
      odds: 3.2,
    },
    {
      id: 2,
      name: "ミラクルジャンプ",
      jockey: "高田潤",
      obstacleRaces: 0,
      obstacleWins: 0,
      jumpQuality: 0,
      aptitudeScore: 72,
      venueRecord: {},
      levelExperience: {},
      flatRecord: { turfMile: 85, dirt1800: 75 },
      courseSpecialty: 0.0,
      odds: 8.5,
    },
    {
      id: 3,
      name: "ステップアップ",
      jockey: "西谷凜",
      obstacleRaces: 1,
      obstacleWins: 0,
      jumpQuality: 3.8,
      aptitudeScore: 78,
      venueRecord: { 福島: "0-0-1-0" },
      levelExperience: { "10-19": 1 },
      flatRecord: { turfMile: 80, dirt1800: 88 },
      courseSpecialty: 0.2,
      odds: 4.1,
    },
  ],
}

export default function AdvancedObstacleAnalyzer() {
  const [selectedVenue, setSelectedVenue] = useState("中山")
  const [selectedDistance, setSelectedDistance] = useState("4100芝")

  const currentLevel = obstacleLevelData[selectedVenue]?.[selectedDistance] || 0
  const venueInfo = racetrackData[selectedVenue]

  const getDifficultyColor = (level: number) => {
    if (level >= 40) return "text-red-600 bg-red-50"
    if (level >= 30) return "text-orange-600 bg-orange-50"
    if (level >= 20) return "text-yellow-600 bg-yellow-50"
    return "text-green-600 bg-green-50"
  }

  const getDifficultyLabel = (level: number) => {
    if (level >= 40) return "最高難度"
    if (level >= 30) return "高難度"
    if (level >= 20) return "中難度"
    return "標準"
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-gray-900 flex items-center justify-center gap-2">
            <Mountain className="text-blue-600" />
            高度障害レース分析システム
          </h1>
          <p className="text-lg text-gray-600">競馬場別難易度レベル × コース特性 × 実績分析</p>
        </div>

        <Card className="bg-white/80 backdrop-blur">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="text-blue-600" />
              コース選択 & 難易度分析
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-4 gap-4 mb-6">
              <div>
                <label className="text-sm font-medium mb-2 block">競馬場</label>
                <Select value={selectedVenue} onValueChange={setSelectedVenue}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(obstacleLevelData).map((venue) => (
                      <SelectItem key={venue} value={venue}>
                        {venue}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">距離・馬場</label>
                <Select value={selectedDistance} onValueChange={setSelectedDistance}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(obstacleLevelData[selectedVenue] || {}).map((distance) => (
                      <SelectItem key={distance} value={distance}>
                        {distance}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col justify-end">
                <div className={`p-3 rounded-lg text-center ${getDifficultyColor(currentLevel)}`}>
                  <div className="text-2xl font-bold">{currentLevel}</div>
                  <div className="text-sm">難易度レベル</div>
                </div>
              </div>
              <div className="flex flex-col justify-end">
                <Badge variant="outline" className="text-center py-2">
                  {getDifficultyLabel(currentLevel)}
                </Badge>
              </div>
            </div>

            {venueInfo && (
              <div className="grid md:grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
                <div>
                  <h4 className="font-semibold mb-2">{venueInfo.name}</h4>
                  <div className="space-y-1 text-sm">
                    <div>📍 {venueInfo.location}</div>
                    <div>🏁 {venueInfo.features.join(" / ")}</div>
                  </div>
                </div>
                <div>
                  <h4 className="font-semibold mb-2">障害コース特徴</h4>
                  <div className="space-y-1 text-sm">
                    {venueInfo.obstacleFeatures.map((feature, idx) => (
                      <div key={idx}>• {feature}</div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Tabs defaultValue="level-analysis" className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="level-analysis">レベル分析</TabsTrigger>
            <TabsTrigger value="venue-comparison">競馬場比較</TabsTrigger>
            <TabsTrigger value="horse-analysis">出走馬分析</TabsTrigger>
            <TabsTrigger value="experience-matrix">経験値マトリックス</TabsTrigger>
            <TabsTrigger value="prediction">AI予測</TabsTrigger>
          </TabsList>

          <TabsContent value="level-analysis" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gauge className="text-purple-600" />
                  障害レベル詳細分析
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div className="text-center">
                    <div className="inline-flex items-center gap-4 p-6 bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl">
                      <div className="text-center">
                        <div className="text-4xl font-bold text-blue-600">{currentLevel}</div>
                        <div className="text-sm text-gray-600">障害レベル</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">{selectedVenue}</div>
                        <div className="text-sm text-gray-600">{selectedDistance}</div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-4">全コース難易度分布</h4>
                    <div className="space-y-2">
                      {Object.entries(obstacleLevelData).map(([venue, distances]) => (
                        <div key={venue} className="space-y-1">
                          <div className="font-medium text-sm">{venue}</div>
                          <div className="flex gap-2 flex-wrap">
                            {Object.entries(distances).map(([distance, level]) => (
                              <div
                                key={`${venue}-${distance}`}
                                className={`px-3 py-1 rounded text-xs font-medium ${
                                  venue === selectedVenue && distance === selectedDistance
                                    ? "bg-blue-600 text-white"
                                    : getDifficultyColor(level)
                                }`}
                              >
                                {distance}: {level}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="p-4 border rounded-lg">
                      <h4 className="font-semibold mb-2 flex items-center gap-2">
                        <Target className="w-4 h-4 text-green-600" />
                        このレベルの特徴
                      </h4>
                      <div className="text-sm space-y-1">
                        {currentLevel >= 40 && (
                          <>
                            <div>• 最高難度の技術的障害</div>
                            <div>• 豊富な経験が必須</div>
                            <div>• スタミナと技術の両立</div>
                          </>
                        )}
                        {currentLevel >= 30 && currentLevel < 40 && (
                          <>
                            <div>• 高い技術力が要求</div>
                            <div>• 中級以上の経験推奨</div>
                            <div>• バランス型が有利</div>
                          </>
                        )}
                        {currentLevel >= 20 && currentLevel < 30 && (
                          <>
                            <div>• 標準的な障害レベル</div>
                            <div>• 初心者でも挑戦可能</div>
                            <div>• 基本技術で対応可能</div>
                          </>
                        )}
                        {currentLevel < 20 && (
                          <>
                            <div>• 入門レベルの障害</div>
                            <div>• 初障害馬でも安心</div>
                            <div>• 平地実績重視</div>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="p-4 border rounded-lg">
                      <h4 className="font-semibold mb-2 flex items-center gap-2">
                        <Info className="w-4 h-4 text-blue-600" />
                        推奨馬の条件
                      </h4>
                      <div className="text-sm space-y-1">
                        {currentLevel >= 40 && (
                          <>
                            <div>• 障害5戦以上の経験</div>
                            <div>• 同レベル帯での実績</div>
                            <div>• 障害専門騎手</div>
                          </>
                        )}
                        {currentLevel >= 30 && currentLevel < 40 && (
                          <>
                            <div>• 障害3戦以上推奨</div>
                            <div>• 平地G3以上の実力</div>
                            <div>• 折り合い重視</div>
                          </>
                        )}
                        {currentLevel >= 20 && currentLevel < 30 && (
                          <>
                            <div>• 障害1戦以上あれば安心</div>
                            <div>• 平地中距離実績</div>
                            <div>• 素直な気性</div>
                          </>
                        )}
                        {currentLevel < 20 && (
                          <>
                            <div>• 初障害でも問題なし</div>
                            <div>• 芝マイル好走歴</div>
                            <div>• 若い馬でも対応可</div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="venue-comparison" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="text-green-600" />
                  競馬場別難易度比較
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(racetrackData).map(([venue, info]) => {
                    const levels = Object.values(obstacleLevelData[venue] || {})
                    const avgLevel =
                      levels.length > 0 ? Math.round(levels.reduce((a, b) => a + b, 0) / levels.length) : 0
                    const maxLevel = Math.max(...levels, 0)
                    const minLevel = Math.min(...levels, 0)

                    return (
                      <div key={venue} className="p-4 border rounded-lg hover:bg-gray-50">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="font-semibold">{info.name}</h4>
                            <div className="text-sm text-gray-600">{info.location}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-lg font-bold text-blue-600">{avgLevel}</div>
                            <div className="text-xs text-gray-600">平均レベル</div>
                          </div>
                        </div>

                        <div className="grid grid-cols-3 gap-4 mb-3">
                          <div className="text-center p-2 bg-red-50 rounded">
                            <div className="font-bold text-red-600">{maxLevel}</div>
                            <div className="text-xs">最高</div>
                          </div>
                          <div className="text-center p-2 bg-blue-50 rounded">
                            <div className="font-bold text-blue-600">{avgLevel}</div>
                            <div className="text-xs">平均</div>
                          </div>
                          <div className="text-center p-2 bg-green-50 rounded">
                            <div className="font-bold text-green-600">{minLevel}</div>
                            <div className="text-xs">最低</div>
                          </div>
                        </div>

                        <div className="text-sm">
                          <div className="font-medium mb-1">特徴:</div>
                          <div className="text-gray-600">{info.obstacleFeatures.join(" / ")}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="horse-analysis" className="space-y-6">
            <div className="grid gap-6">
              {mockRaceData.horses.map((horse) => (
                <Card key={horse.id} className="overflow-hidden">
                  <CardHeader className="bg-gradient-to-r from-blue-50 to-green-50">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-xl">{horse.name}</CardTitle>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">騎手: {horse.jockey}</Badge>
                        <Badge variant="secondary">{horse.odds}倍</Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-6">
                    <div className="grid md:grid-cols-4 gap-6">
                      <div className="space-y-3">
                        <h4 className="font-semibold flex items-center gap-2">
                          <Gauge className="w-4 h-4 text-purple-600" />
                          レベル適性
                        </h4>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-purple-600">{currentLevel}</div>
                          <div className="text-sm text-gray-600 mb-2">今回レベル</div>
                          <div className="text-sm">
                            経験レベル帯:
                            {Object.keys(horse.levelExperience).length > 0 ? (
                              <div className="mt-1">
                                {Object.entries(horse.levelExperience).map(([range, count]) => (
                                  <Badge key={range} variant="outline" className="mr-1 text-xs">
                                    {range}: {count}戦
                                  </Badge>
                                ))}
                              </div>
                            ) : (
                              <div className="text-orange-600 mt-1">未経験</div>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h4 className="font-semibold flex items-center gap-2">
                          <MapPin className="w-4 h-4 text-green-600" />
                          会場実績
                        </h4>
                        <div className="space-y-2">
                          {Object.keys(horse.venueRecord).length > 0 ? (
                            Object.entries(horse.venueRecord).map(([venue, record]) => (
                              <div key={venue} className="text-sm">
                                <div className="font-medium">{venue}</div>
                                <div className="text-gray-600">{record}</div>
                              </div>
                            ))
                          ) : (
                            <div className="text-sm text-orange-600">会場未経験</div>
                          )}
                          <div className="mt-2">
                            <div className="text-xs text-gray-600">コース適性</div>
                            <Progress value={horse.courseSpecialty * 100} className="h-2 mt-1" />
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h4 className="font-semibold flex items-center gap-2">
                          <Activity className="w-4 h-4 text-blue-600" />
                          障害経験
                        </h4>
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span>出走</span>
                            <span className="font-semibold">{horse.obstacleRaces}戦</span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span>勝利</span>
                            <span className="font-semibold">{horse.obstacleWins}勝</span>
                          </div>
                          {horse.jumpQuality > 0 && (
                            <div className="flex justify-between items-center text-sm">
                              <span>飛越評価</span>
                              <div className="flex items-center gap-1">
                                {[1, 2, 3, 4, 5].map((star) => (
                                  <Star
                                    key={star}
                                    className={`w-3 h-3 ${
                                      star <= horse.jumpQuality ? "text-yellow-400 fill-current" : "text-gray-300"
                                    }`}
                                  />
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h4 className="font-semibold flex items-center gap-2">
                          <Eye className="w-4 h-4 text-orange-600" />
                          レベル適合度
                        </h4>
                        <div className="text-center">
                          {(() => {
                            let compatibility = 50
                            const currentRange =
                              currentLevel >= 40
                                ? "40-49"
                                : currentLevel >= 30
                                  ? "30-39"
                                  : currentLevel >= 20
                                    ? "20-29"
                                    : "10-19"

                            if (horse.levelExperience[currentRange]) {
                              compatibility += 30
                            }

                            if (horse.venueRecord[selectedVenue]) {
                              compatibility += 20
                            }

                            if (horse.obstacleRaces === 0 && currentLevel >= 30) {
                              compatibility -= 40
                            } else if (horse.obstacleRaces >= 5) {
                              compatibility += 15
                            }

                            compatibility = Math.max(0, Math.min(100, compatibility))

                            return (
                              <>
                                <div className="text-3xl font-bold text-orange-600 mb-2">{compatibility}%</div>
                                <Progress value={compatibility} className="h-3 mb-2" />
                                <div className="text-xs text-gray-600">
                                  {compatibility >= 80
                                    ? "高適合"
                                    : compatibility >= 60
                                      ? "適合"
                                      : compatibility >= 40
                                        ? "要注意"
                                        : "不適合"}
                                </div>
                              </>
                            )
                          })()}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="experience-matrix" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Route className="text-indigo-600" />
                  レベル別経験値マトリックス
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">馬名</th>
                        <th className="text-center p-2">10-19</th>
                        <th className="text-center p-2">20-29</th>
                        <th className="text-center p-2">30-39</th>
                        <th className="text-center p-2">40-49</th>
                        <th className="text-center p-2">50+</th>
                        <th className="text-center p-2">今回適合度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mockRaceData.horses.map((horse) => (
                        <tr key={horse.id} className="border-b hover:bg-gray-50">
                          <td className="p-2 font-medium">{horse.name}</td>
                          <td className="text-center p-2">
                            <Badge variant={horse.levelExperience["10-19"] ? "default" : "outline"}>
                              {horse.levelExperience["10-19"] || 0}
                            </Badge>
                          </td>
                          <td className="text-center p-2">
                            <Badge variant={horse.levelExperience["20-29"] ? "default" : "outline"}>
                              {horse.levelExperience["20-29"] || 0}
                            </Badge>
                          </td>
                          <td className="text-center p-2">
                            <Badge variant={horse.levelExperience["30-39"] ? "default" : "outline"}>
                              {horse.levelExperience["30-39"] || 0}
                            </Badge>
                          </td>
                          <td className="text-center p-2">
                            <Badge variant={horse.levelExperience["40-49"] ? "default" : "outline"}>
                              {horse.levelExperience["40-49"] || 0}
                            </Badge>
                          </td>
                          <td className="text-center p-2">
                            <Badge variant={horse.levelExperience["50+"] ? "default" : "outline"}>
                              {horse.levelExperience["50+"] || 0}
                            </Badge>
                          </td>
                          <td className="text-center p-2">
                            {(() => {
                              const currentRange =
                                currentLevel >= 40
                                  ? "40-49"
                                  : currentLevel >= 30
                                    ? "30-39"
                                    : currentLevel >= 20
                                      ? "20-29"
                                      : "10-19"
                              const hasExperience = (horse.levelExperience[currentRange] || 0) > 0
                              return (
                                <Badge variant={hasExperience ? "default" : "destructive"}>
                                  {hasExperience ? "適合" : "未経験"}
                                </Badge>
                              )
                            })()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="prediction" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="text-yellow-500" />
                  レベル考慮AI予測
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="p-4 bg-blue-50 rounded-lg">
                    <h4 className="font-semibold mb-2">予測アルゴリズム</h4>
                    <div className="text-sm space-y-1">
                      <div>• 障害レベル適合度: 40%</div>
                      <div>• 会場実績: 25%</div>
                      <div>• 障害経験値: 20%</div>
                      <div>• 平地実績: 10%</div>
                      <div>• 騎手適性: 5%</div>
                    </div>
                  </div>

                  {mockRaceData.horses
                    .sort((a, b) => b.aptitudeScore - a.aptitudeScore)
                    .map((horse, index) => (
                      <div key={horse.id} className="flex items-center justify-between p-4 border rounded-lg">
                        <div className="flex items-center gap-4">
                          <div className="text-2xl font-bold text-gray-400">{index + 1}</div>
                          <div>
                            <div className="font-semibold">{horse.name}</div>
                            <div className="text-sm text-gray-600">
                              レベル適合度: {(() => {
                                const currentRange =
                                  currentLevel >= 40
                                    ? "40-49"
                                    : currentLevel >= 30
                                      ? "30-39"
                                      : currentLevel >= 20
                                        ? "20-29"
                                        : "10-19"
                                return horse.levelExperience[currentRange] ? "高" : "低"
                              })()}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xl font-bold text-blue-600">{horse.aptitudeScore}</div>
                          <div className="text-sm text-gray-600">{horse.odds}倍</div>
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

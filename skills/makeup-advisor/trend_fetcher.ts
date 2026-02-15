#!/usr/bin/env bun
/**
 * 美妆趋势获取器
 *
 * 数据源：
 * 1. 预定义的季节/节日趋势
 * 2. 可手动更新的热门数据
 * 3. 未来：接入小红书/抖音 API
 */

// 2026年美妆趋势数据库
export const MAKEUP_TRENDS = {
  // 热门妆容（定期更新）
  hot: [
    {
      name: "清透水光肌",
      tags: ["韩系", "日常", "学生党"],
      difficulty: 1,
      products: ["气垫", "高光", "定妆喷雾"],
      steps: [
        "妆前保湿打底",
        "轻拍气垫，薄涂两层",
        "T区点涂高光",
        "定妆喷雾锁妆"
      ],
      suitableFor: ["干皮", "混合皮", "所有脸型"],
      instagram_likes: 125000,
      last_updated: "2026-02-10"
    },
    {
      name: "泰式轻混血",
      tags: ["高级感", "欧美风", "立体"],
      difficulty: 2,
      products: ["修容粉", "眉笔", "哑光眼影", "睫毛膏"],
      steps: [
        "野生眉勾勒，眉毛拉长",
        "鼻影+侧影立体修容",
        "大地色眼影晕染",
        "上下睫毛都要刷"
      ],
      suitableFor: ["所有肤质", "圆脸", "方脸"],
      instagram_likes: 98000,
      last_updated: "2026-02-08"
    },
    {
      name: "千金玛利亚",
      tags: ["贵气", "约会", "宴会"],
      difficulty: 3,
      products: ["粉底液", "遮瑕", "红管口红", "眼线液"],
      steps: [
        "精致底妆，遮瑕到位",
        "猫眼眼线，眼尾上挑",
        "腮红斜扫颧骨",
        "正红唇釉，唇峰清晰"
      ],
      suitableFor: ["油皮友好", "所有脸型"],
      instagram_likes: 87000,
      last_updated: "2026-02-05"
    },
    {
      name: "纯欲白开水",
      tags: ["伪素颜", "日常", "减龄"],
      difficulty: 1,
      products: ["有色隔离", "腮红", "睫毛打底", "润唇膏"],
      steps: [
        "有色隔离均匀肤色",
        "腮红点涂眼下+鼻尖",
        "睫毛打底自然卷翘",
        "唇蜜点缀，嘟嘟唇"
      ],
      suitableFor: ["所有肤质", "圆脸", "鹅蛋脸"],
      instagram_likes: 156000,
      last_updated: "2026-02-12"
    },
    {
      name: "复古港风",
      tags: ["90年代", "港星", "经典"],
      difficulty: 2,
      products: ["粉底", "浓眉产品", "红唇", "眼线"],
      steps: [
        "哑光底妆，不追求水光",
        "浓眉+眉峰上挑",
        "全包眼线+深色眼影",
        "雾面红唇，唇线清晰"
      ],
      suitableFor: ["所有肤质", "长脸", "方脸"],
      instagram_likes: 76000,
      last_updated: "2026-02-01"
    }
  ],

  // 节日妆容
  holidays: {
    valentine: {
      name: "情人节甜蜜妆",
      colors: ["粉红", "玫瑰金", "蜜桃"],
      style: "甜美约会",
      key_points: ["粉嫩腮红", "嘟嘟唇", "卧蚕提亮"],
      outfit_match: "连衣裙、高跟鞋"
    },
    christmas: {
      name: "圣诞派对妆",
      colors: ["正红", "金色", "墨绿"],
      style: "闪亮夺目",
      key_points: ["红唇", "金色眼影", "闪片点缀"],
      outfit_match: "小礼服、红裙子"
    },
    chinese_new_year: {
      name: "春节喜庆妆",
      colors: ["正红", "金色", "橙红"],
      style: "喜气洋洋",
      key_points: ["红唇", "金色眼头", "圆润眉形"],
      outfit_match: "旗袍、红色系"
    },
    halloween: {
      name: "万圣节创意妆",
      colors: ["黑色", "橙色", "紫色"],
      style: "创意变装",
      key_points: ["烟熏眼妆", "创意元素", "夸张睫毛"],
      outfit_match: "主题服装"
    }
  },

  // 季节流行色
  seasonal_colors: {
    spring: {
      main: ["珊瑚粉", "薄荷绿", "奶油黄"],
      accent: ["薰衣草紫", "樱花粉"],
      lip: ["水红色", "蜜桃色"]
    },
    summer: {
      main: ["西瓜红", "椰子白", "海蓝色"],
      accent: ["日落橙", "柠檬黄"],
      lip: ["橘红色", "西柚色"]
    },
    fall: {
      main: ["焦糖棕", "酒红色", "橄榄绿"],
      accent: ["南瓜橘", "枫叶红"],
      lip: ["砖红色", "豆沙色"]
    },
    winter: {
      main: ["浆果紫", "森林绿", "宝石蓝"],
      accent: ["香槟金", "银白色"],
      lip: ["梅子色", "正红色"]
    }
  },

  // 产品推荐（按价格档位）
  products: {
    // 粉底
    foundation: {
      luxury: [
        { brand: "Dior", name: "锁妆粉底液", price: 580, rating: 4.8 },
        { brand: "Armani", name: "大师粉底液", price: 680, rating: 4.7 }
      ],
      mid: [
        { brand: "MAC", name: "定制粉底液", price: 320, rating: 4.5 },
        { brand: "NARS", name: "超完美粉底", price: 380, rating: 4.6 }
      ],
      budget: [
        { brand: "美宝莲", name: "FIT ME", price: 99, rating: 4.3 },
        { brand: "完美日记", name: "沁光粉底", price: 89, rating: 4.2 }
      ]
    },
    // 口红
    lipstick: {
      luxury: [
        { brand: "Dior", name: "999", price: 380, color: "正红", rating: 4.9 },
        { brand: "Chanel", name: "58", price: 380, color: "砖红", rating: 4.8 }
      ],
      mid: [
        { brand: "MAC", name: "Ruby Woo", price: 180, color: "复古红", rating: 4.7 },
        { brand: "YSL", name: "小金条21", price: 350, color: "正红", rating: 4.6 }
      ],
      budget: [
        { brand: "花西子", name: "M1311", price: 89, color: "琥珀红", rating: 4.4 },
        { brand: "橘朵", name: "J06", price: 49, color: "砖红", rating: 4.3 }
      ]
    }
  }
};

// 获取当前季节
export function getCurrentSeason(): "spring" | "summer" | "fall" | "winter" {
  const month = new Date().getMonth() + 1;
  if (month >= 3 && month <= 5) return "spring";
  if (month >= 6 && month <= 8) return "summer";
  if (month >= 9 && month <= 11) return "fall";
  return "winter";
}

// 获取热门妆容（按难度筛选）
export function getHotMakeups(difficulty?: 1 | 2 | 3) {
  let results = MAKEUP_TRENDS.hot;
  if (difficulty) {
    results = results.filter(m => m.difficulty === difficulty);
  }
  return results.sort((a, b) => b.instagram_likes - a.instagram_likes);
}

// 获取季节推荐
export function getSeasonalRecommendation() {
  const season = getCurrentSeason();
  const colors = MAKEUP_TRENDS.seasonal_colors[season];
  const hotMakeups = getHotMakeups();

  return {
    season,
    colors,
    recommended_makeups: hotMakeups.slice(0, 3),
    tip: getSeasonalTip(season)
  };
}

function getSeasonalTip(season: string): string {
  const tips: Record<string, string> = {
    spring: "春季万物复苏，适合清新自然的妆容，推荐粉色系和珊瑚色系",
    summer: "夏季炎热，推荐控油持妆，色彩明快活泼",
    fall: "秋季温暖，适合大地色系和暖色调，打造知性气质",
    winter: "冬季干燥，注意保湿，可以尝试深色系和闪亮元素"
  };
  return tips[season] || "";
}

// 获取产品推荐
export function getProductRecommendations(
  category: "foundation" | "lipstick",
  budget: "luxury" | "mid" | "budget"
) {
  return MAKEUP_TRENDS.products[category][budget];
}

// CLI 测试
if (import.meta.main) {
  console.log("🌸 当前季节推荐:");
  console.log(JSON.stringify(getSeasonalRecommendation(), null, 2));
}

#!/usr/bin/env bun
/**
 * Weather Skill - 天气查询
 *
 * 通过 wttr.in API 获取天气 (无需 API Key)
 *
 * 使用:
 *   bun run fetch.ts                  # 默认北京
 *   bun run fetch.ts 上海             # 指定城市
 *   bun run fetch.ts Beijing --en     # 英文
 *   bun run fetch.ts --forecast       # 5天预报
 *
 * 演进记录:
 *   触发: "帮我查看今天北京的天气"
 *   类型: NO_MATCH → 自动开发
 *   日期: 2026-02-02
 */

interface WeatherData {
  location: string;
  temp_c: number;
  feels_like_c: number;
  humidity: number;
  wind_kph: number;
  wind_dir: string;
  condition: string;
  icon: string;
  sunrise: string;
  sunset: string;
  forecast?: ForecastDay[];
}

interface ForecastDay {
  date: string;
  max_c: number;
  min_c: number;
  condition: string;
  icon: string;
}

const WTTR_API = "https://wttr.in";

const CONDITION_ICONS: Record<string, string> = {
  "Sunny": "☀️",
  "Clear": "🌙",
  "Partly cloudy": "⛅",
  "Cloudy": "☁️",
  "Overcast": "🌥️",
  "Mist": "🌫️",
  "Fog": "🌫️",
  "Light rain": "🌦️",
  "Rain": "🌧️",
  "Heavy rain": "⛈️",
  "Snow": "❄️",
  "Thunderstorm": "⛈️",
  "default": "🌡️"
};

function getIcon(condition: string): string {
  for (const [key, icon] of Object.entries(CONDITION_ICONS)) {
    if (condition.toLowerCase().includes(key.toLowerCase())) {
      return icon;
    }
  }
  return CONDITION_ICONS.default;
}

async function fetchWeather(city: string, lang: string = "zh"): Promise<WeatherData | null> {
  try {
    // wttr.in JSON format
    const url = `${WTTR_API}/${encodeURIComponent(city)}?format=j1&lang=${lang}`;
    const res = await fetch(url);
    const data = await res.json() as any;

    if (!data.current_condition?.[0]) {
      return null;
    }

    const current = data.current_condition[0];
    const astro = data.weather?.[0]?.astronomy?.[0];

    const weather: WeatherData = {
      location: data.nearest_area?.[0]?.areaName?.[0]?.value || city,
      temp_c: parseInt(current.temp_C),
      feels_like_c: parseInt(current.FeelsLikeC),
      humidity: parseInt(current.humidity),
      wind_kph: parseInt(current.windspeedKmph),
      wind_dir: current.winddir16Point,
      condition: lang === "zh" ? current.lang_zh?.[0]?.value || current.weatherDesc?.[0]?.value : current.weatherDesc?.[0]?.value,
      icon: getIcon(current.weatherDesc?.[0]?.value || ""),
      sunrise: astro?.sunrise || "N/A",
      sunset: astro?.sunset || "N/A"
    };

    // Add forecast if available
    if (data.weather?.length > 1) {
      weather.forecast = data.weather.slice(0, 5).map((day: any) => ({
        date: day.date,
        max_c: parseInt(day.maxtempC),
        min_c: parseInt(day.mintempC),
        condition: lang === "zh" ? day.hourly?.[4]?.lang_zh?.[0]?.value || day.hourly?.[4]?.weatherDesc?.[0]?.value : day.hourly?.[4]?.weatherDesc?.[0]?.value,
        icon: getIcon(day.hourly?.[4]?.weatherDesc?.[0]?.value || "")
      }));
    }

    return weather;
  } catch (e) {
    console.error("Error fetching weather:", e);
    return null;
  }
}

function formatWindDir(dir: string): string {
  const dirMap: Record<string, string> = {
    "N": "北风", "NNE": "东北偏北", "NE": "东北风", "ENE": "东北偏东",
    "E": "东风", "ESE": "东南偏东", "SE": "东南风", "SSE": "东南偏南",
    "S": "南风", "SSW": "西南偏南", "SW": "西南风", "WSW": "西南偏西",
    "W": "西风", "WNW": "西北偏西", "NW": "西北风", "NNW": "西北偏北"
  };
  return dirMap[dir] || dir;
}

function formatWindSpeed(kph: number): string {
  if (kph < 12) return "1-2级";
  if (kph < 20) return "3级";
  if (kph < 29) return "4级";
  if (kph < 39) return "5级";
  if (kph < 50) return "6级";
  return "7级以上";
}

function printTVS(weather: WeatherData, showForecast: boolean = false) {
  const width = 65;
  const border = "─".repeat(width);

  console.log(`
┌${border}┐
│${`                     ${weather.icon} ${weather.location}天气`.padEnd(width)}│
├${border}┤
│${`  温度      ${weather.temp_c}°C (体感 ${weather.feels_like_c}°C)`.padEnd(width)}│
│${`  天气      ${weather.condition}`.padEnd(width)}│
│${`  湿度      ${weather.humidity}%`.padEnd(width)}│
│${`  风速      ${formatWindDir(weather.wind_dir)} ${formatWindSpeed(weather.wind_kph)}`.padEnd(width)}│
│${`  日出      ${weather.sunrise}  日落 ${weather.sunset}`.padEnd(width)}│`);

  if (showForecast && weather.forecast?.length) {
    console.log(`├${border}┤
│${`  未来 5 天:`.padEnd(width)}│`);
    for (const day of weather.forecast) {
      const dateStr = day.date.slice(5); // MM-DD
      const line = `  ${dateStr} ${day.icon}  ${day.min_c}°C ~ ${day.max_c}°C  ${day.condition?.slice(0, 10) || ''}`;
      console.log(`│${line.padEnd(width)}│`);
    }
  }

  console.log(`└${border}┘

────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: solar-dark
切换风格: /theme <style>`);
}

async function main() {
  const args = process.argv.slice(2);
  const showForecast = args.includes("--forecast") || args.includes("-f");
  const useEnglish = args.includes("--en");

  // Extract city from args
  let city = "北京";
  for (const arg of args) {
    if (!arg.startsWith("-")) {
      city = arg;
      break;
    }
  }

  console.log(`正在获取 ${city} 天气...`);

  const weather = await fetchWeather(city, useEnglish ? "en" : "zh");

  if (!weather) {
    console.error(`无法获取 ${city} 的天气信息`);
    process.exit(1);
  }

  printTVS(weather, showForecast);
}

main().catch(console.error);

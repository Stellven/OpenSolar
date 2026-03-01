#!/usr/bin/env bun
/**
 * Post-Favorite Auto-Distill Hook
 * 当用户保存收藏时，自动触发技能蒸馏
 *
 * 触发条件：
 * - importance >= 7 的高质量收藏
 * - 包含可提取模式的内容
 *
 * 用法：
 *   bun ~/.claude/core/skill-distiller/hooks/post-favorite-distill.ts <favorite_id>
 */

import { distillFromFavorite } from '../distiller';
import { getFavoriteForDistillation, updateSkillStatus, getSkill } from '../db';

const MIN_IMPORTANCE = 7;

async function main() {
  const favoriteId = parseInt(process.argv[2] || '0');

  if (!favoriteId) {
    console.log('用法: bun post-favorite-distill.ts <favorite_id>');
    process.exit(1);
  }

  console.log(`\n🔄 自动蒸馏触发: 收藏 ${favoriteId}`);

  // 1. 获取收藏内容
  const favorite = getFavoriteForDistillation(favoriteId);
  if (!favorite) {
    console.log('❌ 收藏不存在');
    process.exit(1);
  }

  console.log(`   标题: ${favorite.title}`);
  console.log(`   标签: ${favorite.tags.join(', ')}`);

  // 2. 调用蒸馏器
  console.log('\n   调用审判官蒸馏...');
  const result = await distillFromFavorite(favoriteId);

  if (result.success && result.skill) {
    console.log(`\n✅ 蒸馏成功!`);
    console.log(`   技能ID: ${result.skill.skill_id}`);
    console.log(`   名称: ${result.skill.name}`);
    console.log(`   置信度: ${(result.confidence * 100).toFixed(1)}%`);

    // 3. 高置信度技能自动激活
    if (result.confidence >= 0.85) {
      updateSkillStatus(result.skill.skill_id!, 'active');
      console.log(`   🎯 高置信度，已自动激活!`);
    } else {
      console.log(`   ⏳ 等待审核: bun cli.ts approve ${result.skill.skill_id}`);
    }
  } else {
    console.log(`\n⚠️  蒸馏结果: ${result.error || '置信度不足'}`);
    console.log(`   置信度: ${(result.confidence * 100).toFixed(1)}%`);
  }
}

main().catch(console.error);

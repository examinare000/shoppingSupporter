import type { ImagePriority, SiteType } from '@/types/product';

export const DEFAULT_IMAGE_PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

export const SITE_LABEL: Record<SiteType, string> = {
  amazon: 'Amazon',
  rakuten: 'Rakuten',
  yahoo: 'Yahoo!',
};

export const IMAGE_PRIORITY_STORAGE_KEY = 'shoppingSupporter:imagePriority:v1';

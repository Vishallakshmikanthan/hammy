import React, { useState } from "react";
import {
  Apple,
  Droplets,
  Crown,
  Box,
  Flower2,
  Search,
  Trash2,
  RotateCw,
  Check,
  X,
  Plus,
  Minus,
  ChevronUp,
  ChevronDown,
  Sparkles,
  RotateCcw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  AssetCategory,
  AssetManifest,
  CostumeSlot,
  ManifestAssetItem,
  PlacementDraft,
  ShelvesLayoutState,
} from "../types";

export interface AssetShelfDrawerProps {
  manifest: AssetManifest | null;
  layout: ShelvesLayoutState | null;
  busy: boolean;
  statusMessage: string | null;
  placementDraft: PlacementDraft | null;
  onStartPlacement: (item: ManifestAssetItem) => void;
  onUpdatePlacementDraft: (draft: PlacementDraft | null) => void;
  onConfirmPlacement: () => void;
  onOfferFood: (itemId: string, quantity: number) => void;
  onRefillWater: (amountMl: number) => void;
  onEquipCostume: (itemId: string) => void;
  onUnequipCostume: (slot: CostumeSlot | "all") => void;
  onRemovePlacedItem: (objectId: string) => void;
  onResetCleanCage: () => void;
}

const SHELF_META: Array<{
  key: AssetCategory;
  label: string;
  icon: React.FC<{ className?: string }>;
  badge: string;
  description: string;
}> = [
  {
    key: "food",
    label: "1. Food Shelf",
    icon: Apple,
    badge: "HAMSTER-SAFE",
    description: "Select a hamster-safe food & quantity to offer. Leftovers spoil over time.",
  },
  {
    key: "water",
    label: "2. Water Shelf",
    icon: Droplets,
    badge: "VISIBLE LEVEL",
    description: "Refill the bottle/bowl water level or add an extra ceramic water dish.",
  },
  {
    key: "costume",
    label: "3. Costume Shelf",
    icon: Crown,
    badge: "HEAD/NECK/BACK",
    description: "Equip hamster-scale hats, glasses, bow ties, scarves, or backpacks to rig sockets.",
  },
  {
    key: "prop",
    label: "4. Props Shelf",
    icon: Box,
    badge: "COLLISION NAV",
    description: "Opt-in exercise wheel, straight/curved tunnels, hideout, bridge, chew toy, ball, or shelf.",
  },
  {
    key: "decor",
    label: "5. Decor Shelf",
    icon: Flower2,
    badge: "OPT-IN DECOR",
    description: "Opt-in plants, wooden climbing items, moss bedding patches, flags, and picture frames.",
  },
];

export const AssetShelfDrawer: React.FC<AssetShelfDrawerProps> = ({
  manifest,
  layout,
  busy,
  statusMessage,
  placementDraft,
  onStartPlacement,
  onUpdatePlacementDraft,
  onConfirmPlacement,
  onOfferFood,
  onRefillWater,
  onEquipCostume,
  onUnequipCostume,
  onRemovePlacedItem,
  onResetCleanCage,
}) => {
  // Shelves are CLOSED by default per OVERRIDE spec
  const [openShelf, setOpenShelf] = useState<AssetCategory | null>(null);
  const [activeTab, setActiveTab] = useState<"browse" | "in_cage">("browse");
  const [searchQuery, setSearchQuery] = useState("");
  const [foodQty, setFoodQty] = useState<number>(1);
  const [selectedFoodId, setSelectedFoodId] = useState<string | null>(null);

  const items = manifest?.items ?? [];
  const equippedCostumes = layout?.equipped_costumes ?? {};
  const offeredFoods = layout?.offered_foods ?? [];
  const waterSources = layout?.water_sources ?? [];
  const placedItems = layout?.placed_items ?? [];
  const waterLevel = layout?.water_level ?? 0.75;
  const cheekPouchFill = layout?.cheek_pouch_fill ?? 0.0;

  const toggleShelf = (cat: AssetCategory) => {
    if (openShelf === cat) {
      setOpenShelf(null);
    } else {
      setOpenShelf(cat);
      setActiveTab("browse");
    }
  };

  const countInCageForCategory = (cat: AssetCategory): number => {
    if (cat === "food") return offeredFoods.reduce((acc, f) => acc + f.quantity, 0);
    if (cat === "water") return waterSources.length;
    if (cat === "costume") return Object.keys(equippedCostumes).length;
    if (cat === "prop") return placedItems.filter((p) => p.category === "prop").length;
    if (cat === "decor") return placedItems.filter((p) => p.category === "decor").length;
    return 0;
  };

  const filteredShelfItems = items.filter((it) => {
    if (it.category !== openShelf) return false;
    if (openShelf === "food" && !it.hamster_safe) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return it.name.toLowerCase().includes(q) || it.id.toLowerCase().includes(q);
  });

  return (
    <section
      aria-label="Opt-In Asset Shelves Drawer"
      className="glass-card rounded-2xl p-3.5 space-y-3 border border-[#F4EDE0]/15"
      data-testid="asset-shelf-drawer"
    >
      {/* Top Bar: Header + Reset Button + Status Pills */}
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Badge variant="coralSolid" className="px-2.5 py-0.5 text-[11px]">
            <Sparkles className="w-3 h-3 mr-1" />
            OPT-IN ASSET SHELVES
          </Badge>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={onResetCleanCage}
            data-testid="btn-reset-clean-cage"
            className="h-7 px-2 text-[11px] border-[#F4EDE0]/20 text-[#F4EDE0]/80 hover:bg-[#F4EDE0]/10 gap-1 shrink-0"
          >
            <RotateCcw className="w-3 h-3" />
            Reset Clean Cage
          </Button>
        </div>

        <p className="text-[11px] leading-relaxed text-[#F4EDE0]/70">
          Default 3D Habitat: <strong className="text-[#F4EDE0]/90">Hamster, Home, Logs, Food Bowl, Water Tank &amp; Wheel</strong>. Open any shelf to offer food, equip costumes, or place extra props &amp; decor.
        </p>

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className="text-[10px] border-amber-400/40 text-amber-200 font-mono">
            Cheek Pouches: {Math.round(cheekPouchFill * 100)}%
          </Badge>
          <Badge variant="outline" className="text-[10px] border-sky-400/40 text-sky-200 font-mono">
            Water Level: {Math.round(waterLevel * 100)}%
          </Badge>
        </div>
      </div>

      {/* 5 Separate Shelf Toggle Buttons (Vertical Lateral Stack) */}
      <div className="flex flex-col gap-1.5" data-testid="shelf-category-buttons">
        {SHELF_META.map((shelf) => {
          const Icon = shelf.icon;
          const isOpen = openShelf === shelf.key;
          const inCageCount = countInCageForCategory(shelf.key);
          return (
            <button
              key={shelf.key}
              type="button"
              onClick={() => toggleShelf(shelf.key)}
              data-testid={`shelf-btn-${shelf.key}`}
              className={`flex items-center justify-between px-3 py-2 rounded-xl border text-left transition-all ${
                isOpen
                  ? "bg-[#FF6B5B] text-[#14213D] border-[#FF6B5B] font-bold shadow-coral-glow"
                  : "bg-[#0B1325]/65 text-[#F4EDE0] border-[#F4EDE0]/15 hover:border-[#FF6B5B]/50 hover:bg-[#0B1325]/90"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <Icon className={`w-4 h-4 shrink-0 ${isOpen ? "text-[#14213D]" : "text-[#FF6B5B]"}`} />
                <span className="text-xs font-semibold truncate">{shelf.label}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={`text-[10px] font-mono ${isOpen ? "text-[#14213D]/80" : "text-[#F4EDE0]/55"}`}
                >
                  {inCageCount} in cage
                </span>
                {isOpen ? <ChevronUp className="w-4 h-4 shrink-0" /> : <ChevronDown className="w-4 h-4 shrink-0" />}
              </div>
            </button>
          );
        })}
      </div>

      {/* Interactive Placement Mode Bar (shown when placing or moving a prop/decor item) */}
      {placementDraft && (
        <div
          className="rounded-xl bg-emerald-950/60 border border-emerald-400/50 p-3 space-y-2.5"
          data-testid="placement-mode-bar"
        >
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="outline" className="border-emerald-400 text-emerald-300 text-[10px]">
                PLACEMENT MODE
              </Badge>
              <strong className="text-xs text-[#F4EDE0]">
                {placementDraft.editingObjectId ? `Move ${placementDraft.item.name}` : `Place ${placementDraft.item.name}`}
              </strong>
            </div>
            <div className="text-[11px] font-mono text-emerald-200">
              [{placementDraft.pose_xyz_m[0].toFixed(2)}m, {placementDraft.pose_xyz_m[1].toFixed(2)}m] • Rot{" "}
              {Math.round((placementDraft.rotation_y_rad * 180) / Math.PI)}°
            </div>
            <p className="text-[11px] text-[#F4EDE0]/75">
              Adjust X / Y position within cage bounds and rotation, then confirm.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-[#F4EDE0] flex items-center gap-2">
              <span className="w-5 font-mono text-[11px]">X:</span>
              <input
                type="range"
                min={-0.40}
                max={0.40}
                step={0.02}
                value={placementDraft.pose_xyz_m[0]}
                data-testid="placement-slider-x"
                className="flex-1"
                onChange={(e) =>
                  onUpdatePlacementDraft({
                    ...placementDraft,
                    pose_xyz_m: [Number(e.target.value), placementDraft.pose_xyz_m[1], placementDraft.pose_xyz_m[2]],
                  })
                }
              />
            </label>
            <label className="text-xs text-[#F4EDE0] flex items-center gap-2">
              <span className="w-5 font-mono text-[11px]">Y:</span>
              <input
                type="range"
                min={-0.16}
                max={0.16}
                step={0.02}
                value={placementDraft.pose_xyz_m[1]}
                data-testid="placement-slider-y"
                className="flex-1"
                onChange={(e) =>
                  onUpdatePlacementDraft({
                    ...placementDraft,
                    pose_xyz_m: [placementDraft.pose_xyz_m[0], Number(e.target.value), placementDraft.pose_xyz_m[2]],
                  })
                }
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              data-testid="btn-rotate-prop"
              onClick={() =>
                onUpdatePlacementDraft({
                  ...placementDraft,
                  rotation_y_rad: Number(((placementDraft.rotation_y_rad + Math.PI / 4) % (Math.PI * 2)).toFixed(4)),
                })
              }
              className="gap-1 text-[11px] h-7 px-2 border-emerald-400/40 text-emerald-200"
            >
              <RotateCw className="w-3 h-3" />
              Rotate 45°
            </Button>
            <Button
              type="button"
              variant="coral"
              size="sm"
              disabled={busy}
              data-testid="btn-confirm-placement"
              onClick={onConfirmPlacement}
              className="gap-1 text-[11px] h-7 px-2.5 flex-1"
            >
              <Check className="w-3 h-3" />
              Confirm Placement
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              data-testid="btn-cancel-placement"
              onClick={() => onUpdatePlacementDraft(null)}
              className="gap-1 text-[11px] h-7 px-2 border-[#F4EDE0]/25 text-[#F4EDE0]"
            >
              <X className="w-3 h-3" />
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Status Toast */}
      {statusMessage && (
        <div
          className="rounded-xl bg-[#0B1325]/80 border border-[#FF6B5B]/40 px-3 py-2 text-[11px] text-[#F4EDE0] flex items-center justify-between"
          data-testid="shelf-status-message"
        >
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Expanded Shelf Drawer Content (Only rendered when a shelf is open -> lazy loads thumbnails only when open!) */}
      {openShelf && (
        <div
          className="rounded-2xl bg-[#0B1325]/85 border border-[#F4EDE0]/15 p-3 space-y-3"
          data-testid={`shelf-drawer-${openShelf}`}
        >
          {/* Shelf Header: Title + Search + Browse / In Cage Now Tabs + Category Quick Controls */}
          <div className="space-y-2.5 border-b border-[#F4EDE0]/10 pb-2.5">
            <div>
              <div className="flex items-center justify-between gap-2">
                <h4 className="font-display text-base text-[#F4EDE0]">
                  {SHELF_META.find((s) => s.key === openShelf)?.label}
                </h4>
                <Badge variant="outline" className="text-[10px] border-[#FF6B5B]/40 text-[#FF6B5B] shrink-0">
                  {SHELF_META.find((s) => s.key === openShelf)?.badge}
                </Badge>
              </div>
              <p className="text-[11px] text-[#F4EDE0]/65 mt-0.5">
                {SHELF_META.find((s) => s.key === openShelf)?.description}
              </p>
            </div>

            <div className="space-y-2">
              {/* Search Box */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-[#F4EDE0]/50 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search shelf..."
                  data-testid="shelf-search-input"
                  className="w-full pl-8 pr-3 py-1.5 rounded-full bg-[#14213D] border border-[#F4EDE0]/20 text-xs text-[#F4EDE0] placeholder:text-[#F4EDE0]/40 focus:outline-none focus:border-[#FF6B5B]"
                />
              </div>

              {/* Browse vs In Cage Now Tabs */}
              <div className="rounded-full bg-[#14213D] p-0.5 border border-[#F4EDE0]/15 grid grid-cols-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("browse")}
                  data-testid="tab-browse-shelf"
                  className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-all text-center ${
                    activeTab === "browse" ? "bg-[#FF6B5B] text-[#14213D] font-bold" : "text-[#F4EDE0]/75"
                  }`}
                >
                  Browse ({filteredShelfItems.length})
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("in_cage")}
                  data-testid="tab-in-cage-now"
                  className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-all text-center ${
                    activeTab === "in_cage" ? "bg-[#FF6B5B] text-[#14213D] font-bold" : "text-[#F4EDE0]/75"
                  }`}
                >
                  In cage now ({countInCageForCategory(openShelf)})
                </button>
              </div>

              {/* Category-Specific Controls */}
              {openShelf === "water" && (
                <Button
                  type="button"
                  variant="coral"
                  size="sm"
                  disabled={busy}
                  data-testid="btn-refill-water"
                  onClick={() => onRefillWater(150)}
                  className="w-full text-xs gap-1.5 h-8"
                >
                  <Droplets className="w-3.5 h-3.5" />
                  Refill Water (100%)
                </Button>
              )}

              {openShelf === "costume" && Object.keys(equippedCostumes).length > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  data-testid="btn-unequip-all-costumes"
                  onClick={() => onUnequipCostume("all")}
                  className="w-full text-xs border-[#FF6B5B]/50 text-[#FF6B5B] hover:bg-[#FF6B5B]/15 gap-1 h-8"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Unequip All
                </Button>
              )}
            </div>
          </div>

          {/* TAB 1: BROWSE SHELF GRID */}
          {activeTab === "browse" && (
            <div className="space-y-2.5">
              {/* Quantity selector bar for Food shelf */}
              {openShelf === "food" && (
                <div className="flex items-center justify-between gap-2 rounded-xl bg-[#14213D]/80 px-2.5 py-2 border border-[#F4EDE0]/10">
                  <span className="text-[11px] text-[#F4EDE0]/85">
                    Portion Qty: <strong className="text-[#FF6B5B] font-mono">{foodQty}x</strong>
                  </span>
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setFoodQty((q) => Math.max(1, q - 1))}
                      className="h-6 w-6 p-0 border-[#F4EDE0]/20 text-[#F4EDE0]"
                    >
                      <Minus className="w-3 h-3" />
                    </Button>
                    <span className="font-mono text-xs px-1.5 text-[#F4EDE0]" data-testid="food-qty-display">
                      {foodQty}
                    </span>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setFoodQty((q) => Math.min(5, q + 1))}
                      className="h-6 w-6 p-0 border-[#F4EDE0]/20 text-[#F4EDE0]"
                    >
                      <Plus className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 max-h-[380px] overflow-y-auto pr-0.5">
                {filteredShelfItems.map((item) => {
                  const isEquipped =
                    item.category === "costume" &&
                    item.attachment_slot &&
                    equippedCostumes[item.attachment_slot as CostumeSlot]?.item_id === item.id;

                  return (
                    <div
                      key={item.id}
                      data-testid={`shelf-item-card-${item.id}`}
                      className={`rounded-xl border p-2.5 flex flex-col justify-between gap-2 transition-all ${
                        isEquipped || selectedFoodId === item.id
                          ? "bg-[#FF6B5B]/20 border-[#FF6B5B]"
                          : "bg-[#14213D]/65 border-[#F4EDE0]/12 hover:border-[#F4EDE0]/35"
                      }`}
                    >
                      <div className="space-y-1.5">
                        <div className="relative aspect-square w-full rounded-lg bg-[#0B1325]/90 overflow-hidden flex items-center justify-center border border-[#F4EDE0]/10">
                          <img
                            src={item.thumbnail_url}
                            alt={item.name}
                            loading="lazy"
                            className="w-full h-full object-contain p-1.5"
                          />
                          <span className="absolute top-1 right-1 px-1.5 py-0.5 rounded bg-[#0B1325]/85 text-[9px] font-mono text-[#F4EDE0]/75">
                            {item.origin_label}
                          </span>
                          {item.attachment_slot && item.category === "costume" && (
                            <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-[#FF6B5B]/90 text-[#14213D] font-bold text-[9px] font-mono">
                              {item.attachment_slot}
                            </span>
                          )}
                        </div>
                        <div className="text-xs font-semibold text-[#F4EDE0] leading-tight">{item.name}</div>
                        <div className="text-[10px] font-mono text-[#F4EDE0]/55">
                          {item.triangle_count} tris • {(item.file_size_bytes / 1024).toFixed(0)} KB
                        </div>
                      </div>

                      {/* Action button per category */}
                      {item.category === "food" && (
                        <Button
                          type="button"
                          variant="coral"
                          size="sm"
                          disabled={busy}
                          data-testid={`btn-offer-${item.id}`}
                          onClick={() => {
                            setSelectedFoodId(item.id);
                            onOfferFood(item.id, foodQty);
                          }}
                          className="w-full text-xs py-1 h-7"
                        >
                          Offer ({foodQty}x)
                        </Button>
                      )}

                      {item.category === "water" && (
                        <div className="flex flex-col gap-1">
                          <Button
                            type="button"
                            variant="coral"
                            size="sm"
                            disabled={busy}
                            data-testid={`btn-refill-${item.id}`}
                            onClick={() => onRefillWater(150)}
                            className="w-full text-xs py-1 h-7"
                          >
                            Refill Level
                          </Button>
                          {item.id === "water_bowl" && (
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              data-testid={`btn-place-${item.id}`}
                              onClick={() => onStartPlacement(item)}
                              className="w-full text-[11px] py-0.5 h-6 border-[#F4EDE0]/25 text-[#F4EDE0]"
                            >
                              Place Dish
                            </Button>
                          )}
                        </div>
                      )}

                      {item.category === "costume" && (
                        <Button
                          type="button"
                          variant={isEquipped ? "outline" : "coral"}
                          size="sm"
                          disabled={busy}
                          data-testid={`btn-costume-${item.id}`}
                          onClick={() =>
                            isEquipped && item.attachment_slot
                              ? onUnequipCostume(item.attachment_slot as CostumeSlot)
                              : onEquipCostume(item.id)
                          }
                          className={`w-full text-xs py-1 h-7 ${
                            isEquipped ? "border-[#FF6B5B] text-[#FF6B5B]" : ""
                          }`}
                        >
                          {isEquipped ? "Unequip" : "Equip"}
                        </Button>
                      )}

                      {(item.category === "prop" || item.category === "decor") && (
                        <Button
                          type="button"
                          variant="coral"
                          size="sm"
                          disabled={busy}
                          data-testid={`btn-place-${item.id}`}
                          onClick={() => onStartPlacement(item)}
                          className="w-full text-xs py-1 h-7"
                        >
                          Place in Cage
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: IN CAGE NOW */}
          {activeTab === "in_cage" && (
            <div className="space-y-2 max-h-[340px] overflow-y-auto pr-0.5" data-testid="in-cage-now-list">
              {openShelf === "food" && (
                <>
                  {offeredFoods.length === 0 ? (
                    <p className="text-xs text-[#F4EDE0]/60 py-2">No food currently offered in the cage.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {offeredFoods.map((f) => (
                        <div
                          key={f.object_id}
                          className="rounded-xl bg-[#14213D]/80 border border-[#F4EDE0]/15 p-2.5 flex items-center justify-between gap-2 text-xs"
                        >
                          <div className="min-w-0">
                            <div className="font-semibold text-[#F4EDE0] truncate">
                              {f.name} ({f.quantity}x remaining)
                            </div>
                            <div className="text-[10px] font-mono text-[#F4EDE0]/60">
                              Pos: [{f.pose_xyz_m[0].toFixed(2)}, {f.pose_xyz_m[1].toFixed(2)}] •{" "}
                              {f.spoiled ? "SPOILED" : "Fresh"}
                            </div>
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => onRemovePlacedItem(f.object_id)}
                            className="h-7 text-xs border-[#FF6B5B]/40 text-[#FF6B5B] shrink-0"
                          >
                            Clear
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {openShelf === "water" && (
                <div className="flex flex-col gap-2">
                  {waterSources.map((w) => (
                    <div
                      key={w.object_id}
                      className="rounded-xl bg-[#14213D]/80 border border-[#F4EDE0]/15 p-2.5 flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="min-w-0">
                        <div className="font-semibold text-[#F4EDE0] truncate">{w.name}</div>
                        <div className="text-[11px] font-mono text-sky-300">
                          Level: {Math.round(w.water_level * 100)}% ({Math.round(w.water_level * w.capacity_ml)} /{" "}
                          {w.capacity_ml} ml)
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="coral"
                        size="sm"
                        onClick={() => onRefillWater(150)}
                        className="h-7 text-xs shrink-0"
                      >
                        Refill 100%
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {openShelf === "costume" && (
                <>
                  {Object.keys(equippedCostumes).length === 0 ? (
                    <p className="text-xs text-[#F4EDE0]/60 py-2">No costumes currently equipped on Hammy.</p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {Object.values(equippedCostumes).map((eq) =>
                        eq ? (
                          <div
                            key={eq.slot}
                            className="rounded-xl bg-[#14213D]/80 border border-[#F4EDE0]/15 p-2.5 flex items-center justify-between gap-2 text-xs"
                          >
                            <div className="min-w-0">
                              <div className="font-semibold text-[#F4EDE0] truncate">{eq.name}</div>
                              <div className="text-[10px] font-mono text-[#FF6B5B]">Slot: {eq.slot}</div>
                            </div>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              data-testid={`btn-unequip-slot-${eq.slot}`}
                              onClick={() => onUnequipCostume(eq.slot)}
                              className="h-7 text-xs border-[#FF6B5B]/40 text-[#FF6B5B] shrink-0"
                            >
                              Remove
                            </Button>
                          </div>
                        ) : null
                      )}
                    </div>
                  )}
                </>
              )}

              {(openShelf === "prop" || openShelf === "decor") && (
                <>
                  {placedItems.filter((p) => p.category === openShelf).length === 0 ? (
                    <p className="text-xs text-[#F4EDE0]/60 py-2">
                      No {openShelf} items currently in the cage. Switch to Browse to place one!
                    </p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {placedItems
                        .filter((p) => p.category === openShelf)
                        .map((placed) => {
                          const meta = items.find((i) => i.id === placed.item_id);
                          return (
                            <div
                              key={placed.object_id}
                              data-testid={`in-cage-item-${placed.item_id}`}
                              className="rounded-xl bg-[#14213D]/80 border border-[#F4EDE0]/15 p-2.5 space-y-2 text-xs"
                            >
                              <div>
                                <div className="font-semibold text-[#F4EDE0]">{placed.name}</div>
                                <div className="text-[10px] font-mono text-[#F4EDE0]/60">
                                  Pos: [{placed.pose_xyz_m[0].toFixed(2)}m, {placed.pose_xyz_m[1].toFixed(2)}m] • Rot{" "}
                                  {Math.round((placed.rotation_y_rad * 180) / Math.PI)}°
                                </div>
                              </div>
                              <div className="flex items-center gap-1.5">
                                {meta && (
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    data-testid={`btn-move-${placed.item_id}`}
                                    onClick={() =>
                                      onUpdatePlacementDraft({
                                        item: meta,
                                        pose_xyz_m: placed.pose_xyz_m,
                                        rotation_y_rad: placed.rotation_y_rad,
                                        editingObjectId: placed.object_id,
                                      })
                                    }
                                    className="h-7 text-xs border-[#F4EDE0]/25 text-[#F4EDE0] flex-1"
                                  >
                                    Move
                                  </Button>
                                )}
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  data-testid={`btn-remove-${placed.item_id}`}
                                  onClick={() => onRemovePlacedItem(placed.object_id)}
                                  className="h-7 text-xs border-[#FF6B5B]/40 text-[#FF6B5B] flex-1"
                                >
                                  Send to Shelf
                                </Button>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
};

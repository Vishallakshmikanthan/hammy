import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AssetShelfDrawer } from "../AssetShelfDrawer";
import type { AssetManifest, ShelvesLayoutState } from "../../types";

const MOCK_MANIFEST: AssetManifest = {
  version: "1.0.0",
  generated_at: "2026-11-19T00:00:00Z",
  hamster_reference_length_m: 0.15,
  total_assets: 5,
  items: [
    {
      id: "food_carrot_piece",
      name: "Fresh Carrot Piece",
      category: "food",
      file_path: "assets/web/food_carrot_piece.glb",
      web_url: "/assets/items/food_carrot_piece.glb",
      thumbnail: "assets/thumbnails/food_carrot_piece.png",
      thumbnail_url: "/assets/thumbnails/food_carrot_piece.png",
      scale: [0.02, 0.02, 0.02],
      pivot: "pickup_pivot",
      attachment_slot: "food_hold_socket",
      hamster_safe: true,
      safety_notes: "Safe fresh vegetable",
      licence: "CC0-1.0",
      source: "Generated in Blender",
      author: "HAMMY",
      origin_label: "GENERATED",
      polygon_count: 144,
      triangle_count: 144,
      file_size_bytes: 12040,
      collision_radius_m: 0.015,
    },
    {
      id: "water_bottle",
      name: "Ball-Spout Water Bottle",
      category: "water",
      file_path: "assets/web/water_bottle.glb",
      web_url: "/assets/items/water_bottle.glb",
      thumbnail: "assets/thumbnails/water_bottle.png",
      thumbnail_url: "/assets/thumbnails/water_bottle.png",
      scale: [0.05, 0.05, 0.14],
      pivot: "base_center",
      attachment_slot: null,
      hamster_safe: true,
      safety_notes: "Standard water source",
      licence: "CC0-1.0",
      source: "Generated in Blender",
      author: "HAMMY",
      origin_label: "GENERATED",
      polygon_count: 420,
      triangle_count: 420,
      file_size_bytes: 24500,
      collision_radius_m: 0.03,
    },
    {
      id: "costume_party_hat",
      name: "Festive Party Hat",
      category: "costume",
      file_path: "assets/web/costume_party_hat.glb",
      web_url: "/assets/items/costume_party_hat.glb",
      thumbnail: "assets/thumbnails/costume_party_hat.png",
      thumbnail_url: "/assets/thumbnails/costume_party_hat.png",
      scale: [0.03, 0.03, 0.04],
      pivot: "head_slot",
      attachment_slot: "head_slot",
      hamster_safe: true,
      safety_notes: "Visual costume",
      licence: "CC0-1.0",
      source: "Generated in Blender",
      author: "HAMMY",
      origin_label: "GENERATED",
      polygon_count: 196,
      triangle_count: 196,
      file_size_bytes: 15200,
      collision_radius_m: 0.02,
    },
    {
      id: "prop_tunnel_straight",
      name: "Straight Hollow Bark Tunnel",
      category: "prop",
      file_path: "assets/web/prop_tunnel_straight.glb",
      web_url: "/assets/items/prop_tunnel_straight.glb",
      thumbnail: "assets/thumbnails/prop_tunnel_straight.png",
      thumbnail_url: "/assets/thumbnails/prop_tunnel_straight.png",
      scale: [0.16, 0.08, 0.08],
      pivot: "base_center",
      attachment_slot: null,
      hamster_safe: true,
      safety_notes: "Safe tunnel",
      licence: "CC0-1.0",
      source: "Generated in Blender",
      author: "HAMMY",
      origin_label: "GENERATED",
      polygon_count: 384,
      triangle_count: 384,
      file_size_bytes: 28400,
      collision_radius_m: 0.065,
    },
    {
      id: "decor_plant_fern",
      name: "Terrarium Fern Cluster",
      category: "decor",
      file_path: "assets/web/decor_plant_fern.glb",
      web_url: "/assets/items/decor_plant_fern.glb",
      thumbnail: "assets/thumbnails/decor_plant_fern.png",
      thumbnail_url: "/assets/thumbnails/decor_plant_fern.png",
      scale: [0.08, 0.08, 0.09],
      pivot: "base_center",
      attachment_slot: null,
      hamster_safe: true,
      safety_notes: "Safe decor",
      licence: "CC0-1.0",
      source: "Generated in Blender",
      author: "HAMMY",
      origin_label: "GENERATED",
      polygon_count: 312,
      triangle_count: 312,
      file_size_bytes: 19800,
      collision_radius_m: 0.035,
    },
  ],
};

const CLEAN_LAYOUT: ShelvesLayoutState = {
  pet_id: "pet_hammy_01",
  sim_time_sec: 120,
  cheek_pouch_fill: 0,
  water_level: 0.75,
  equipped_costumes: {},
  offered_foods: [],
  water_sources: [
    {
      object_id: "prop_bottle_main",
      item_id: "water_bottle",
      name: "Ball-Spout Water Bottle",
      pose_xyz_m: [0.433, -0.02, 0.183],
      water_level: 0.75,
      capacity_ml: 150,
    },
  ],
  placed_items: [],
};

describe("Step 6 Opt-In AssetShelfDrawer UI", () => {
  it("renders all 5 shelves closed by default and opens Food, Costume, and Props shelves on click", () => {
    const onOfferFood = vi.fn();
    const onRefillFood = vi.fn();
    const onRefillWater = vi.fn();
    const onEquipCostume = vi.fn();
    const onUnequipCostume = vi.fn();
    const onStartPlacement = vi.fn();

    render(
      <AssetShelfDrawer
        manifest={MOCK_MANIFEST}
        layout={{ ...CLEAN_LAYOUT, food_level: 0.45 }}
        busy={false}
        statusMessage={null}
        placementDraft={null}
        onStartPlacement={onStartPlacement}
        onUpdatePlacementDraft={vi.fn()}
        onConfirmPlacement={vi.fn()}
        onOfferFood={onOfferFood}
        onRefillFood={onRefillFood}
        onRefillWater={onRefillWater}
        onEquipCostume={onEquipCostume}
        onUnequipCostume={onUnequipCostume}
        onRemovePlacedItem={vi.fn()}
        onResetCleanCage={vi.fn()}
      />
    );

    // Closed by default: no shelf drawer is open
    expect(screen.queryByTestId("shelf-drawer-food")).toBeNull();
    expect(screen.queryByTestId("shelf-drawer-costume")).toBeNull();
    expect(screen.queryByTestId("shelf-drawer-prop")).toBeNull();

    // 1. Open Food Shelf -> offer carrot & refill food bowl
    fireEvent.click(screen.getByTestId("shelf-btn-food"));
    expect(screen.getByTestId("shelf-drawer-food")).toBeDefined();
    expect(screen.getByTestId("shelf-item-card-food_carrot_piece")).toBeDefined();
    fireEvent.click(screen.getByTestId("btn-offer-food_carrot_piece"));
    expect(onOfferFood).toHaveBeenCalledWith("food_carrot_piece", 1);
    fireEvent.click(screen.getByTestId("btn-refill-food"));
    expect(onRefillFood).toHaveBeenCalledWith(25);

    // 2. Open Costume Shelf -> equip party hat
    fireEvent.click(screen.getByTestId("shelf-btn-costume"));
    expect(screen.getByTestId("shelf-drawer-costume")).toBeDefined();
    expect(screen.getByTestId("shelf-item-card-costume_party_hat")).toBeDefined();
    fireEvent.click(screen.getByTestId("btn-costume-costume_party_hat"));
    expect(onEquipCostume).toHaveBeenCalledWith("costume_party_hat");

    // 3. Open Props Shelf -> start placement of tunnel
    fireEvent.click(screen.getByTestId("shelf-btn-prop"));
    expect(screen.getByTestId("shelf-drawer-prop")).toBeDefined();
    expect(screen.getByTestId("shelf-item-card-prop_tunnel_straight")).toBeDefined();
    fireEvent.click(screen.getByTestId("btn-place-prop_tunnel_straight"));
    expect(onStartPlacement).toHaveBeenCalledWith(MOCK_MANIFEST.items[3]);
  });
});

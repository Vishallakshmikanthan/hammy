import React from "react";
import { ScrollText, Database } from "lucide-react";
import { BehaviourType, EventOrigin, WorldEvent } from "../types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface EventsFeedProps {
  events: WorldEvent[];
}

export const EventsFeed: React.FC<EventsFeedProps> = ({ events }) => {
  const getOriginBadge = (origin: EventOrigin) => {
    switch (origin) {
      case "observed_physics":
        return (
          <Badge variant="default" data-testid="origin-badge">
            observed_physics
          </Badge>
        );
      case "sampled_from_skill_model":
        return (
          <Badge variant="cream" data-testid="origin-badge">
            sampled_from_skill_model
          </Badge>
        );
      case "rule":
      default:
        return (
          <Badge variant="warning" data-testid="origin-badge">
            rule
          </Badge>
        );
    }
  };

  const getBehaviourBadge = (behaviour: BehaviourType) => {
    switch (behaviour) {
      case "learned":
        return (
          <Badge variant="success" data-testid="behaviour-badge">
            learned
          </Badge>
        );
      case "scripted":
        return (
          <Badge variant="cream" data-testid="behaviour-badge">
            scripted
          </Badge>
        );
      case "rule":
      default:
        return (
          <Badge variant="warning" data-testid="behaviour-badge">
            rule
          </Badge>
        );
    }
  };

  return (
    <Card className="relative overflow-hidden" data-testid="events-feed">
      <CardHeader className="pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#FF6B5B] mb-1">
            <ScrollText className="h-3.5 w-3.5" />
            Immutable World Ledger
          </div>
          <CardTitle className="font-display text-2xl font-normal tracking-wide text-[#F4EDE0]">
            Authoritative Events Feed
          </CardTitle>
          <CardDescription>
            Last {events.length} events recorded in PostgreSQL. Every row links to an immutable record.
          </CardDescription>
        </div>

        <Badge variant="coralSolid" className="px-3.5 py-1 text-xs" data-testid="events-count">
          <Database className="h-3 w-3" />
          {events.length} Events
        </Badge>
      </CardHeader>

      <CardContent>
        {events.length === 0 ? (
          <div className="rounded-2xl border border-[#F4EDE0]/12 bg-[#0B1325]/50 p-8 text-center text-xs text-[#F4EDE0]/65">
            No events recorded yet for this pet.
          </div>
        ) : (
          <div className="rounded-2xl border border-[#F4EDE0]/15 bg-[#0B1325]/45 overflow-hidden backdrop-blur-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Record ID</TableHead>
                  <TableHead>Sim Time (s)</TableHead>
                  <TableHead>Tick</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Skill</TableHead>
                  <TableHead>Origin</TableHead>
                  <TableHead>Behaviour</TableHead>
                  <TableHead>Payload</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((ev) => (
                  <TableRow key={ev.event_id} data-testid="event-item">
                    <TableCell className="font-mono text-[#F4EDE0]/60" title={ev.event_id}>
                      {ev.event_id.slice(0, 16)}...
                    </TableCell>
                    <TableCell className="font-mono text-[#F4EDE0]">
                      {ev.sim_time_sec.toFixed(1)}
                    </TableCell>
                    <TableCell className="font-mono text-[#FF6B5B]">
                      #{ev.world_tick}
                    </TableCell>
                    <TableCell className="font-semibold text-[#F4EDE0]">
                      {ev.event_type}
                    </TableCell>
                    <TableCell className="text-[#F4EDE0]/80">
                      {ev.skill_name || "—"}
                    </TableCell>
                    <TableCell>{getOriginBadge(ev.origin)}</TableCell>
                    <TableCell>{getBehaviourBadge(ev.behaviour_type)}</TableCell>
                    <TableCell className="max-w-[260px] truncate font-mono text-[11px] text-[#F4EDE0]/70">
                      {JSON.stringify(ev.payload || {})}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

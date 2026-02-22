import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import type { EmergencyProfile } from '@/hooks/useEmergencyProfile';

const INCIDENT_TYPES = [
  { value: 'being_followed', label: 'Being followed' },
  { value: 'witnessed_crime', label: 'Witnessed crime' },
  { value: 'medical_emergency', label: 'Medical emergency' },
  { value: 'assault', label: 'Assault / threat' },
  { value: 'unsafe_situation', label: 'Unsafe situation' },
  { value: 'other', label: 'Other' },
];

const SEVERITIES = [
  { value: 'CRITICAL', label: 'Critical' },
  { value: 'HIGH', label: 'High' },
  { value: 'MEDIUM', label: 'Medium' },
];

interface EmergencyProfileModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profile: EmergencyProfile;
  onSave: (updates: Partial<EmergencyProfile>) => void;
}

export default function EmergencyProfileModal({
  open,
  onOpenChange,
  profile,
  onSave,
}: EmergencyProfileModalProps) {
  const [form, setForm] = useState(profile);

  useEffect(() => {
    if (open) setForm(profile);
  }, [open, profile]);

  const handleSave = () => {
    if (!form.name.trim()) {
      toast.error('Name is required for emergency calls');
      return;
    }
    onSave(form);
    toast.success('Emergency profile saved');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-primary" />
            Emergency Profile
          </DialogTitle>
          <DialogDescription>
            This information is automatically sent to the 911 operator when you tap
            Emergency. Stored locally on your device.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {/* Name */}
          <div>
            <Label htmlFor="ep-name">Full name *</Label>
            <Input
              id="ep-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Your full name"
              className="mt-1"
            />
          </div>

          {/* Age */}
          <div>
            <Label htmlFor="ep-age">Age</Label>
            <Input
              id="ep-age"
              value={form.age}
              onChange={(e) => setForm({ ...form, age: e.target.value })}
              placeholder="e.g. 21"
              className="mt-1"
            />
          </div>

          {/* Medical conditions */}
          <div>
            <Label htmlFor="ep-med">Medical conditions</Label>
            <Textarea
              id="ep-med"
              value={form.medicalConditions}
              onChange={(e) => setForm({ ...form, medicalConditions: e.target.value })}
              placeholder="Allergies, medications, disabilities, etc."
              className="mt-1 resize-none"
              rows={2}
            />
          </div>

          {/* Emergency contact */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ep-ec-name">Emergency contact</Label>
              <Input
                id="ep-ec-name"
                value={form.emergencyContactName}
                onChange={(e) => setForm({ ...form, emergencyContactName: e.target.value })}
                placeholder="Name"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="ep-ec-phone">Phone</Label>
              <Input
                id="ep-ec-phone"
                value={form.emergencyContactPhone}
                onChange={(e) => setForm({ ...form, emergencyContactPhone: e.target.value })}
                placeholder="+1-555-..."
                className="mt-1"
              />
            </div>
          </div>

          {/* Defaults */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label>Default incident type</Label>
              <Select
                value={form.defaultIncidentType}
                onValueChange={(v) => setForm({ ...form, defaultIncidentType: v })}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INCIDENT_TYPES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Default severity</Label>
              <Select
                value={form.defaultSeverity}
                onValueChange={(v) => setForm({ ...form, defaultSeverity: v })}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Demo phone number for judges / testing */}
          <div>
            <Label htmlFor="ep-demo-phone">Demo call number</Label>
            <Input
              id="ep-demo-phone"
              value={form.demoPhoneNumber}
              onChange={(e) => setForm({ ...form, demoPhoneNumber: e.target.value })}
              placeholder="+1-555-123-4567"
              className="mt-1"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Enter your phone number to receive the AI emergency call yourself during testing.
              Leave blank to use the default demo line.
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} className="bg-primary">
              Save Profile
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
